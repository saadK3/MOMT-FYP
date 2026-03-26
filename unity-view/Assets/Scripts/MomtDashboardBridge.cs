using System;
using System.Collections;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.Rendering;

public sealed class MomtDashboardBridge : MonoBehaviour
{
    private const float LiveVehicleExpirySeconds = 2.0f;
    private const float LabelVerticalOffset = 0.95f;
    private const float SymbolVerticalOffset = 0.24f;
    private const float JourneySampleScale = 0.55f;
    private const float JourneyLineHeight = 0.18f;

    private static readonly Color NeutralBodyColor = new Color(0.13f, 0.17f, 0.23f, 1f);
    private static readonly Color HaloColor = new Color(0.85f, 0.92f, 1f, 0.95f);

    private static readonly string[] SurfaceShaderCandidates =
    {
        "Legacy Shaders/Diffuse",
        "Legacy Shaders/VertexLit",
        "Standard",
    };

    private static readonly string[] LineShaderCandidates =
    {
        "Legacy Shaders/Diffuse",
        "Legacy Shaders/VertexLit",
        "Sprites/Default",
    };

    private static Font _labelFont;

#if UNITY_WEBGL && !UNITY_EDITOR
    [DllImport("__Internal")]
    private static extern void MomtUnity_OnReady();

    [DllImport("__Internal")]
    private static extern void MomtUnity_OnVehicleEvent(string payload);
#else
    private static void MomtUnity_OnReady() { }
    private static void MomtUnity_OnVehicleEvent(string payload) { }
#endif

    private readonly Dictionary<int, VehicleVisual> _liveVehicles = new();
    private readonly List<GameObject> _journeyVisuals = new();
    private readonly Dictionary<string, Material> _segmentMaterials = new();

    private MomtOrbitCamera _orbitCamera;
    private Camera _mainCamera;
    private GameObject _groundPlane;
    private Material _groundMaterial;
    private MomtVehicleMarker _hoveredMarker;
    private string _loadedTextureUrl;
    private string _currentViewMode = "3d-live";

    private void Start()
    {
        EnsureSceneScaffold();
        MomtUnity_OnReady();
    }

    public void ApplyDashboardState(string json)
    {
        if (string.IsNullOrWhiteSpace(json))
        {
            return;
        }

        var payload = JsonUtility.FromJson<DashboardStatePayload>(json);
        if (payload == null)
        {
            return;
        }

        EnsureSceneScaffold();
        _currentViewMode = string.IsNullOrWhiteSpace(payload.viewMode)
            ? "3d-live"
            : payload.viewMode;

        if (!string.IsNullOrWhiteSpace(payload.mapTextureUrl))
        {
            StartCoroutine(LoadGroundTexture(payload.mapTextureUrl));
        }

        ApplyLiveVehicles(
            payload.liveVehicles,
            payload.timestamp,
            payload.selectedGlobalId
        );

        if (_currentViewMode == "3d-journey")
        {
            ApplyJourney(payload.selectedJourney);
        }
        else
        {
            ClearJourneyVisuals();
            _orbitCamera?.SetTarget(Vector3.zero);
        }
    }

    private void Update()
    {
        HandleVehiclePointerInteraction();
    }

    private void EnsureSceneScaffold()
    {
        if (_mainCamera == null)
        {
            _mainCamera = Camera.main;
        }

        if (_mainCamera != null && _orbitCamera == null)
        {
            _orbitCamera = _mainCamera.GetComponent<MomtOrbitCamera>();
        }

        if (_groundPlane != null)
        {
            return;
        }

        _groundPlane = new GameObject("GroundPlane");
        var meshFilter = _groundPlane.AddComponent<MeshFilter>();
        meshFilter.sharedMesh = MomtCoordinateMapper.CreateGroundMesh();

        var meshRenderer = _groundPlane.AddComponent<MeshRenderer>();
        _groundMaterial = CreateSurfaceMaterial(new Color(0.16f, 0.18f, 0.24f, 1f));
        _groundMaterial.mainTextureScale = Vector2.one;
        meshRenderer.material = _groundMaterial;
        meshRenderer.shadowCastingMode = ShadowCastingMode.Off;
        meshRenderer.receiveShadows = true;
    }

    private IEnumerator LoadGroundTexture(string textureUrl)
    {
        if (string.Equals(_loadedTextureUrl, textureUrl, StringComparison.OrdinalIgnoreCase))
        {
            yield break;
        }

        using var request = UnityWebRequestTexture.GetTexture(textureUrl);
        yield return request.SendWebRequest();

        if (request.result != UnityWebRequest.Result.Success)
        {
            Debug.LogWarning($"Failed to load map texture: {request.error}");
            yield break;
        }

        var texture = DownloadHandlerTexture.GetContent(request);
        texture.wrapMode = TextureWrapMode.Clamp;
        texture.filterMode = FilterMode.Bilinear;
        _groundMaterial.mainTexture = texture;
        _loadedTextureUrl = textureUrl;
    }

    private void ApplyLiveVehicles(
        LiveVehiclePayload[] vehicles,
        float timestamp,
        int selectedGlobalId
    )
    {
        var seenIds = new HashSet<int>();
        var selectedBounds = new Bounds(Vector3.zero, Vector3.one * 8f);
        var hasSelectionBounds = false;

        if (vehicles != null)
        {
            foreach (var vehicle in vehicles)
            {
                if (vehicle == null || vehicle.footprint == null || vehicle.footprint.Length != 8)
                {
                    continue;
                }

                seenIds.Add(vehicle.globalId);
                var visual = GetOrCreateVehicle(vehicle.globalId);
                var isSelected = selectedGlobalId > 0 && vehicle.globalId == selectedGlobalId;
                UpdateVehicleVisual(visual, vehicle, timestamp, isSelected);

                var isVisible =
                    _currentViewMode == "3d-live" ||
                    vehicle.globalId == selectedGlobalId;
                visual.Root.SetActive(isVisible);

                if (vehicle.globalId == selectedGlobalId)
                {
                    if (!hasSelectionBounds)
                    {
                        selectedBounds = new Bounds(
                            visual.Root.transform.position,
                            Vector3.one * 6f
                        );
                        hasSelectionBounds = true;
                    }
                    else
                    {
                        selectedBounds.Encapsulate(visual.Root.transform.position);
                    }
                }
            }
        }

        foreach (var pair in new List<KeyValuePair<int, VehicleVisual>>(_liveVehicles))
        {
            var visual = pair.Value;
            if (!seenIds.Contains(pair.Key) && timestamp - visual.LastSeen > LiveVehicleExpirySeconds)
            {
                Destroy(visual.Root);
                _liveVehicles.Remove(pair.Key);
            }
        }

        if (_currentViewMode == "3d-journey" && hasSelectionBounds)
        {
            _orbitCamera?.FrameBounds(selectedBounds);
        }
    }

    private VehicleVisual GetOrCreateVehicle(int globalId)
    {
        if (_liveVehicles.TryGetValue(globalId, out var existing))
        {
            return existing;
        }

        var root = new GameObject($"Vehicle_{globalId}");
        root.name = $"Vehicle_{globalId}";

        var body = GameObject.CreatePrimitive(PrimitiveType.Cube);
        body.name = "Body";
        body.transform.SetParent(root.transform, false);
        Destroy(body.GetComponent<Collider>());

        var renderer = body.GetComponent<MeshRenderer>();
        renderer.material = CreateSurfaceMaterial(NeutralBodyColor);
        renderer.shadowCastingMode = ShadowCastingMode.On;
        renderer.receiveShadows = true;

        var marker = root.AddComponent<MomtVehicleMarker>();
        marker.GlobalId = globalId;
        var hitCollider = root.AddComponent<BoxCollider>();

        var labelText = CreateVehicleLabel(root.transform);
        labelText.gameObject.SetActive(false);

        var halo = CreateVehicleHalo(root.transform);
        halo.SetActive(false);

        var directionIndicator = CreateDirectionIndicator(root.transform);

        var visual = new VehicleVisual
        {
            Root = root,
            Renderer = renderer,
            Marker = marker,
            HitCollider = hitCollider,
            LabelText = labelText,
            Halo = halo,
            HaloRenderer = halo.GetComponent<MeshRenderer>(),
            DirectionIndicator = directionIndicator.transform,
            DirectionIndicatorRenderer = directionIndicator.GetComponent<MeshRenderer>(),
        };

        _liveVehicles[globalId] = visual;
        return visual;
    }

    private void UpdateVehicleVisual(
        VehicleVisual visual,
        LiveVehiclePayload payload,
        float timestamp,
        bool isSelected
    )
    {
        var geometry = MomtCoordinateMapper.ComputeVehicleGeometry(payload.footprint);
        var measuredHeight = MomtCoordinateMapper.GetVehicleHeight(payload.className);
        var height = Mathf.Max(0.9f, measuredHeight * 0.78f);
        var position = MomtCoordinateMapper.CentroidToWorld(payload.centroid);
        var classKey = NormalizeVehicleClass(payload.className);
        var accentColor = GetClassAccentColor(classKey);

        visual.Root.transform.position = new Vector3(position.x, 0f, position.z);
        visual.Root.transform.rotation = Quaternion.Euler(0f, geometry.HeadingDegrees, 0f);
        visual.Renderer.transform.localPosition = new Vector3(0f, height * 0.5f, 0f);
        visual.Renderer.transform.localRotation = Quaternion.identity;
        visual.Renderer.transform.localScale = new Vector3(
            geometry.Width,
            height,
            geometry.Length
        );
        if (visual.HitCollider != null)
        {
            visual.HitCollider.center = new Vector3(0f, height * 0.55f, 0f);
            visual.HitCollider.size = new Vector3(
                Mathf.Max(geometry.Width * 1.55f, 1.8f),
                Mathf.Max(height * 1.9f, 1.6f),
                Mathf.Max(geometry.Length * 1.45f, 2.4f)
            );
        }

        UpdateVehicleAdornment(visual, classKey, payload.globalId, height);
        ConfigureHalo(visual, geometry.Width, geometry.Length);
        ConfigureDirectionIndicator(visual, geometry.Length, height);

        visual.Marker.CameraStateLabel = payload.cameraStateLabel ?? "Unknown";
        visual.Marker.HasCameraChanged = payload.hasCameraChanged;
        visual.Marker.VehicleClass = payload.className ?? "unknown";
        visual.Marker.SetSelected(isSelected);
        visual.AccentColor = accentColor;
        visual.LastSeen = timestamp;

        ApplyVehiclePresentation(visual);
    }

    private void UpdateVehicleAdornment(
        VehicleVisual visual,
        string classKey,
        int globalId,
        float vehicleHeight
    )
    {
        if (!string.Equals(visual.ClassKey, classKey, StringComparison.Ordinal))
        {
            if (visual.Symbol != null)
            {
                Destroy(visual.Symbol);
                visual.Symbol = null;
                visual.SymbolRenderers = Array.Empty<MeshRenderer>();
            }

            visual.Symbol = CreateVehicleSymbol(classKey, visual.Root.transform);
            visual.SymbolRenderers = visual.Symbol.GetComponentsInChildren<MeshRenderer>();
            visual.ClassKey = classKey;
        }

        if (visual.Symbol != null)
        {
            ConfigureVehicleSymbol(visual.Symbol.transform, vehicleHeight);
        }

        if (visual.LabelText != null)
        {
            visual.LabelText.text = $"G{globalId}";
            visual.LabelText.transform.localPosition = new Vector3(
                0f,
                vehicleHeight + LabelVerticalOffset,
                0f
            );
        }
    }

    private void ConfigureHalo(VehicleVisual visual, float width, float length)
    {
        if (visual.Halo == null)
        {
            return;
        }

        visual.Halo.transform.localPosition = new Vector3(0f, 0.035f, 0f);
        visual.Halo.transform.localRotation = Quaternion.identity;
        visual.Halo.transform.localScale = new Vector3(
            Mathf.Clamp(width * 1.45f, 2.2f, 8f),
            0.03f,
            Mathf.Clamp(length * 1.25f, 2.8f, 14f)
        );
    }

    private void ConfigureDirectionIndicator(
        VehicleVisual visual,
        float vehicleLength,
        float vehicleHeight
    )
    {
        if (visual.DirectionIndicator == null)
        {
            return;
        }

        visual.DirectionIndicator.localPosition = new Vector3(
            0f,
            (vehicleHeight * 0.08f) + 0.08f,
            (vehicleLength * 0.5f) - 0.18f
        );
        visual.DirectionIndicator.localRotation = Quaternion.identity;
        visual.DirectionIndicator.localScale = new Vector3(
            0.28f,
            Mathf.Clamp(vehicleHeight * 0.18f, 0.14f, 0.32f),
            Mathf.Clamp(vehicleLength * 0.2f, 0.32f, 0.85f)
        );
    }

    private void ApplyVehiclePresentation(VehicleVisual visual)
    {
        var emphasis = visual.Marker.IsSelected
            ? 0.62f
            : visual.Marker.IsHovered
                ? 0.42f
                : 0.14f;

        var bodyColor = Color.Lerp(NeutralBodyColor, visual.AccentColor, emphasis);
        visual.Renderer.material.color = bodyColor;
        if (visual.Renderer.material.HasProperty("_EmissionColor"))
        {
            visual.Renderer.material.EnableKeyword("_EMISSION");
            visual.Renderer.material.SetColor(
                "_EmissionColor",
                visual.AccentColor * (visual.Marker.IsSelected ? 0.22f : visual.Marker.IsHovered ? 0.12f : 0.04f)
            );
        }

        SetRenderersColor(
            visual.SymbolRenderers,
            visual.AccentColor,
            visual.Marker.IsSelected ? 0.34f : visual.Marker.IsHovered ? 0.2f : 0.1f
        );

        if (visual.DirectionIndicatorRenderer != null)
        {
            var directionColor = Color.Lerp(Color.white, visual.AccentColor, 0.55f);
            visual.DirectionIndicatorRenderer.material.color = directionColor;
            if (visual.DirectionIndicatorRenderer.material.HasProperty("_EmissionColor"))
            {
                visual.DirectionIndicatorRenderer.material.EnableKeyword("_EMISSION");
                visual.DirectionIndicatorRenderer.material.SetColor(
                    "_EmissionColor",
                    directionColor * 0.15f
                );
            }
        }

        var showInfo = visual.Marker.IsHovered || visual.Marker.IsSelected;
        if (visual.LabelText != null)
        {
            visual.LabelText.gameObject.SetActive(showInfo);
            visual.LabelText.color = showInfo ? Color.white : new Color(1f, 1f, 1f, 0f);
        }

        if (visual.Halo != null)
        {
            visual.Halo.SetActive(showInfo);
            if (visual.HaloRenderer != null)
            {
                var haloColor = Color.Lerp(HaloColor, visual.AccentColor, 0.35f);
                visual.HaloRenderer.material.color = haloColor;
                if (visual.HaloRenderer.material.HasProperty("_EmissionColor"))
                {
                    visual.HaloRenderer.material.EnableKeyword("_EMISSION");
                    visual.HaloRenderer.material.SetColor(
                        "_EmissionColor",
                        haloColor * (visual.Marker.IsSelected ? 0.45f : 0.24f)
                    );
                }
            }
        }
    }

    private void SetRenderersColor(Renderer[] renderers, Color color, float emissionIntensity)
    {
        if (renderers == null)
        {
            return;
        }

        foreach (var renderer in renderers)
        {
            if (renderer == null)
            {
                continue;
            }

            renderer.material.color = color;
            if (renderer.material.HasProperty("_EmissionColor"))
            {
                renderer.material.EnableKeyword("_EMISSION");
                renderer.material.SetColor("_EmissionColor", color * emissionIntensity);
            }
        }
    }

    private void ApplyJourney(JourneyPayload journey)
    {
        ClearJourneyVisuals();
        if (journey == null || journey.segments == null || journey.segments.Length == 0)
        {
            return;
        }

        var bounds = new Bounds(Vector3.zero, Vector3.one * 10f);
        var hasBounds = false;

        foreach (var segment in journey.segments)
        {
            if (segment?.points == null || segment.points.Length < 2)
            {
                continue;
            }

            var segmentObject = new GameObject($"JourneySegment_{segment.cameraLabel}");
            var line = segmentObject.AddComponent<LineRenderer>();
            line.positionCount = segment.points.Length;
            line.widthCurve = AnimationCurve.Constant(0f, 1f, 1.12f);
            line.material = GetSegmentMaterial(segment.cameraLabel);
            line.numCapVertices = 5;
            line.numCornerVertices = 5;
            line.useWorldSpace = true;

            for (var index = 0; index < segment.points.Length; index += 1)
            {
                var point = segment.points[index];
                var world = MomtCoordinateMapper.CentroidToWorld(point.centroid);
                world.y = JourneyLineHeight;
                line.SetPosition(index, world);

                if (!hasBounds)
                {
                    bounds = new Bounds(world, Vector3.one * 4f);
                    hasBounds = true;
                }
                else
                {
                    bounds.Encapsulate(world);
                }
            }

            _journeyVisuals.Add(segmentObject);
        }

        AddJourneySampleVisuals(journey, ref bounds, ref hasBounds);

        if (journey.transitions != null)
        {
            foreach (var transition in journey.transitions)
            {
                AddTransitionMarker(transition, ref bounds, ref hasBounds);
            }
        }

        if (hasBounds)
        {
            _orbitCamera?.FrameBounds(bounds);
        }
    }

    private void AddJourneySampleVisuals(
        JourneyPayload journey,
        ref Bounds bounds,
        ref bool hasBounds
    )
    {
        if (journey.pathPoints == null || journey.pathPoints.Length == 0)
        {
            return;
        }

        var pathPoints = journey.pathPoints;
        var midSampleCount = Mathf.Clamp(pathPoints.Length / 10, 0, 8);
        if (midSampleCount > 0)
        {
            var step = Mathf.Max(1, pathPoints.Length / (midSampleCount + 1));
            for (var index = step; index < pathPoints.Length - 1; index += step)
            {
                AddJourneyVehicleSample(
                    $"JourneySample_{index}",
                    pathPoints[index],
                    JourneySampleScale,
                    null,
                    ref bounds,
                    ref hasBounds
                );
            }
        }

        AddJourneyVehicleSample(
            "JourneyStart",
            pathPoints[0],
            0.74f,
            $"G{journey.globalId} Start",
            ref bounds,
            ref hasBounds
        );
        AddJourneyVehicleSample(
            "JourneyEnd",
            pathPoints[pathPoints.Length - 1],
            0.86f,
            $"G{journey.globalId}",
            ref bounds,
            ref hasBounds
        );
    }

    private void AddJourneyVehicleSample(
        string name,
        JourneyPointPayload point,
        float scaleMultiplier,
        string labelText,
        ref Bounds bounds,
        ref bool hasBounds
    )
    {
        var root = new GameObject(name);
        root.name = name;

        var body = GameObject.CreatePrimitive(PrimitiveType.Cube);
        body.name = "Body";
        body.transform.SetParent(root.transform, false);
        Destroy(body.GetComponent<Collider>());

        var renderer = body.GetComponent<MeshRenderer>();
        var classKey = NormalizeVehicleClass(point.className);
        var accentColor = GetClassAccentColor(classKey);
        renderer.material = CreateSurfaceMaterial(
            Color.Lerp(NeutralBodyColor, accentColor, 0.35f)
        );
        renderer.shadowCastingMode = ShadowCastingMode.Off;
        renderer.receiveShadows = true;

        var height = Mathf.Max(
            0.72f,
            MomtCoordinateMapper.GetVehicleHeight(point.className) * 0.62f * scaleMultiplier
        );
        var position = MomtCoordinateMapper.CentroidToWorld(point.centroid);

        if (point.footprint != null && point.footprint.Length == 8)
        {
            var geometry = MomtCoordinateMapper.ComputeVehicleGeometry(point.footprint);
            root.transform.position = new Vector3(position.x, 0f, position.z);
            root.transform.rotation = Quaternion.Euler(
                0f,
                geometry.HeadingDegrees,
                0f
            );
            body.transform.localPosition = new Vector3(0f, height * 0.5f, 0f);
            body.transform.localRotation = Quaternion.identity;
            body.transform.localScale = new Vector3(
                geometry.Width * scaleMultiplier,
                height,
                geometry.Length * scaleMultiplier
            );
        }
        else
        {
            root.transform.position = new Vector3(position.x, 0f, position.z);
            root.transform.rotation = Quaternion.Euler(
                0f,
                MomtCoordinateMapper.HeadingDataToWorld(point.headingDeg),
                0f
            );
            body.transform.localPosition = new Vector3(0f, height * 0.5f, 0f);
            body.transform.localRotation = Quaternion.identity;
            body.transform.localScale = new Vector3(
                1.35f * scaleMultiplier,
                height,
                3.4f * scaleMultiplier
            );
        }

        var symbol = CreateVehicleSymbol(classKey, root.transform);
        ConfigureVehicleSymbol(symbol.transform, height);
        SetRenderersColor(
            symbol.GetComponentsInChildren<MeshRenderer>(),
            accentColor,
            0.18f
        );

        var directionIndicator = CreateDirectionIndicator(root.transform);
        directionIndicator.transform.localPosition = new Vector3(
            0f,
            (height * 0.08f) + 0.08f,
            (body.transform.localScale.z * 0.5f) - 0.16f
        );
        directionIndicator.transform.localRotation = Quaternion.identity;
        directionIndicator.transform.localScale = new Vector3(0.22f, 0.14f, 0.42f);
        var directionRenderer = directionIndicator.GetComponent<MeshRenderer>();
        directionRenderer.material.color = Color.Lerp(Color.white, accentColor, 0.55f);

        if (!string.IsNullOrWhiteSpace(labelText))
        {
            var label = CreateVehicleLabel(root.transform);
            label.text = labelText;
            label.transform.localPosition = new Vector3(
                0f,
                height + LabelVerticalOffset,
                0f
            );
            label.characterSize *= 1.05f;
        }

        _journeyVisuals.Add(root);

        if (!hasBounds)
        {
            bounds = new Bounds(root.transform.position, Vector3.one * 5f);
            hasBounds = true;
        }
        else
        {
            bounds.Encapsulate(root.transform.position);
        }
    }

    private void AddTransitionMarker(
        JourneyTransitionPayload transition,
        ref Bounds bounds,
        ref bool hasBounds
    )
    {
        var marker = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        marker.name = $"Transition_{transition.timestamp:0.0}";
        marker.transform.localScale = new Vector3(0.58f, 0.95f, 0.58f);
        var world = MomtCoordinateMapper.CentroidToWorld(transition.centroid);
        marker.transform.position = new Vector3(world.x, 0.95f, world.z);
        Destroy(marker.GetComponent<Collider>());

        var renderer = marker.GetComponent<MeshRenderer>();
        renderer.material = CreateSurfaceMaterial(new Color(0.97f, 0.98f, 1f, 1f));
        if (renderer.material.HasProperty("_EmissionColor"))
        {
            renderer.material.EnableKeyword("_EMISSION");
            renderer.material.SetColor(
                "_EmissionColor",
                new Color(0.35f, 0.45f, 0.9f, 1f) * 0.35f
            );
        }

        _journeyVisuals.Add(marker);

        if (!hasBounds)
        {
            bounds = new Bounds(marker.transform.position, Vector3.one * 4f);
            hasBounds = true;
        }
        else
        {
            bounds.Encapsulate(marker.transform.position);
        }
    }

    private GameObject CreateVehicleSymbol(string classKey, Transform parent)
    {
        var root = new GameObject("TypeSymbol");
        root.transform.SetParent(parent, false);

        switch (classKey)
        {
            case "sedan":
                AddSymbolPrimitive(
                    root.transform,
                    PrimitiveType.Sphere,
                    Vector3.zero,
                    Vector3.zero,
                    new Vector3(0.46f, 0.22f, 0.62f)
                );
                AddSymbolPrimitive(
                    root.transform,
                    PrimitiveType.Cube,
                    new Vector3(0f, -0.11f, 0f),
                    Vector3.zero,
                    new Vector3(0.56f, 0.10f, 0.30f)
                );
                break;
            case "suv_hatchback":
                AddSymbolPrimitive(
                    root.transform,
                    PrimitiveType.Cube,
                    Vector3.zero,
                    new Vector3(0f, 45f, 0f),
                    new Vector3(0.54f, 0.20f, 0.54f)
                );
                AddSymbolPrimitive(
                    root.transform,
                    PrimitiveType.Cube,
                    new Vector3(0f, 0.12f, 0f),
                    Vector3.zero,
                    new Vector3(0.14f, 0.16f, 0.14f)
                );
                break;
            case "pickup":
                AddSymbolPrimitive(
                    root.transform,
                    PrimitiveType.Cube,
                    new Vector3(0f, 0f, 0.08f),
                    Vector3.zero,
                    new Vector3(0.50f, 0.16f, 0.24f)
                );
                AddSymbolPrimitive(
                    root.transform,
                    PrimitiveType.Cube,
                    new Vector3(0f, -0.02f, -0.18f),
                    Vector3.zero,
                    new Vector3(0.50f, 0.08f, 0.22f)
                );
                break;
            case "semi_truck":
                AddSymbolPrimitive(
                    root.transform,
                    PrimitiveType.Cube,
                    new Vector3(0f, 0f, 0.18f),
                    Vector3.zero,
                    new Vector3(0.22f, 0.18f, 0.24f)
                );
                AddSymbolPrimitive(
                    root.transform,
                    PrimitiveType.Cube,
                    new Vector3(0f, -0.02f, -0.12f),
                    Vector3.zero,
                    new Vector3(0.44f, 0.12f, 0.42f)
                );
                break;
            case "van":
                AddSymbolPrimitive(
                    root.transform,
                    PrimitiveType.Cube,
                    Vector3.zero,
                    Vector3.zero,
                    new Vector3(0.48f, 0.24f, 0.34f)
                );
                AddSymbolPrimitive(
                    root.transform,
                    PrimitiveType.Cube,
                    new Vector3(0f, 0.12f, 0f),
                    Vector3.zero,
                    new Vector3(0.28f, 0.08f, 0.24f)
                );
                break;
            case "bus":
                AddSymbolPrimitive(
                    root.transform,
                    PrimitiveType.Cube,
                    Vector3.zero,
                    Vector3.zero,
                    new Vector3(0.58f, 0.18f, 0.28f)
                );
                AddSymbolPrimitive(
                    root.transform,
                    PrimitiveType.Cube,
                    new Vector3(0f, 0.11f, 0f),
                    Vector3.zero,
                    new Vector3(0.44f, 0.06f, 0.16f)
                );
                break;
            case "bike":
                AddSymbolPrimitive(
                    root.transform,
                    PrimitiveType.Cylinder,
                    new Vector3(-0.14f, -0.04f, 0f),
                    new Vector3(90f, 0f, 0f),
                    new Vector3(0.12f, 0.04f, 0.12f)
                );
                AddSymbolPrimitive(
                    root.transform,
                    PrimitiveType.Cylinder,
                    new Vector3(0.14f, -0.04f, 0f),
                    new Vector3(90f, 0f, 0f),
                    new Vector3(0.12f, 0.04f, 0.12f)
                );
                AddSymbolPrimitive(
                    root.transform,
                    PrimitiveType.Capsule,
                    new Vector3(0f, 0.08f, 0f),
                    new Vector3(0f, 0f, 90f),
                    new Vector3(0.14f, 0.14f, 0.10f)
                );
                break;
            case "negative":
                AddSymbolPrimitive(
                    root.transform,
                    PrimitiveType.Cube,
                    Vector3.zero,
                    new Vector3(0f, 0f, 45f),
                    new Vector3(0.42f, 0.08f, 0.12f)
                );
                AddSymbolPrimitive(
                    root.transform,
                    PrimitiveType.Cube,
                    Vector3.zero,
                    new Vector3(0f, 0f, -45f),
                    new Vector3(0.42f, 0.08f, 0.12f)
                );
                break;
            case "other":
                AddSymbolPrimitive(
                    root.transform,
                    PrimitiveType.Cube,
                    Vector3.zero,
                    new Vector3(45f, 45f, 0f),
                    new Vector3(0.34f, 0.34f, 0.34f)
                );
                break;
            default:
                AddSymbolPrimitive(
                    root.transform,
                    PrimitiveType.Sphere,
                    Vector3.zero,
                    Vector3.zero,
                    new Vector3(0.34f, 0.18f, 0.34f)
                );
                break;
        }

        return root;
    }

    private GameObject AddSymbolPrimitive(
        Transform parent,
        PrimitiveType primitiveType,
        Vector3 localPosition,
        Vector3 localEulerAngles,
        Vector3 localScale
    )
    {
        var primitive = GameObject.CreatePrimitive(primitiveType);
        primitive.transform.SetParent(parent, false);
        primitive.transform.localPosition = localPosition;
        primitive.transform.localRotation = Quaternion.Euler(localEulerAngles);
        primitive.transform.localScale = localScale;
        primitive.name = $"SymbolPart_{primitiveType}";

        Destroy(primitive.GetComponent<Collider>());

        var renderer = primitive.GetComponent<MeshRenderer>();
        renderer.material = CreateSurfaceMaterial(Color.white);
        renderer.shadowCastingMode = ShadowCastingMode.Off;
        renderer.receiveShadows = false;

        return primitive;
    }

    private void ConfigureVehicleSymbol(Transform symbolTransform, float vehicleHeight)
    {
        symbolTransform.localPosition = new Vector3(
            0f,
            (vehicleHeight * 0.5f) + SymbolVerticalOffset,
            0f
        );
        symbolTransform.localRotation = Quaternion.identity;
        symbolTransform.localScale = Vector3.one;
    }

    private GameObject CreateVehicleHalo(Transform parent)
    {
        var halo = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        halo.name = "SelectionHalo";
        halo.transform.SetParent(parent, false);
        Destroy(halo.GetComponent<Collider>());

        var renderer = halo.GetComponent<MeshRenderer>();
        renderer.material = CreateSurfaceMaterial(HaloColor);
        renderer.shadowCastingMode = ShadowCastingMode.Off;
        renderer.receiveShadows = false;

        return halo;
    }

    private GameObject CreateDirectionIndicator(Transform parent)
    {
        var nose = GameObject.CreatePrimitive(PrimitiveType.Cube);
        nose.name = "DirectionIndicator";
        nose.transform.SetParent(parent, false);
        Destroy(nose.GetComponent<Collider>());

        var renderer = nose.GetComponent<MeshRenderer>();
        renderer.material = CreateSurfaceMaterial(Color.white);
        renderer.shadowCastingMode = ShadowCastingMode.Off;
        renderer.receiveShadows = false;

        return nose;
    }

    private string NormalizeVehicleClass(string className)
    {
        return className switch
        {
            "Sedan" => "sedan",
            "SUV / Hatchback" => "suv_hatchback",
            "Pickup / Minitruck" => "pickup",
            "Truck" => "semi_truck",
            "Truck / Semi-Truck" => "semi_truck",
            "Bus" => "bus",
            "Motorcycle" => "bike",
            "Bike" => "bike",
            "Van" => "van",
            "Negative" => "negative",
            "Other" => "other",
            _ => "unknown",
        };
    }

    private Color GetClassAccentColor(string classKey)
    {
        return classKey switch
        {
            "sedan" => new Color(0.36f, 0.77f, 0.97f, 1f),
            "suv_hatchback" => new Color(0.48f, 0.88f, 0.56f, 1f),
            "pickup" => new Color(1.00f, 0.77f, 0.34f, 1f),
            "semi_truck" => new Color(0.96f, 0.42f, 0.44f, 1f),
            "bus" => new Color(0.66f, 0.58f, 0.97f, 1f),
            "bike" => new Color(0.33f, 0.90f, 0.86f, 1f),
            "van" => new Color(0.95f, 0.82f, 0.49f, 1f),
            "negative" => new Color(0.92f, 0.92f, 0.92f, 1f),
            "other" => new Color(0.89f, 0.58f, 0.95f, 1f),
            _ => new Color(0.86f, 0.89f, 0.95f, 1f),
        };
    }

    private TextMesh CreateVehicleLabel(Transform parent)
    {
        var labelObject = new GameObject("VehicleLabel");
        labelObject.transform.SetParent(parent, false);
        labelObject.AddComponent<MomtBillboardText>();

        var textMesh = labelObject.AddComponent<TextMesh>();
        textMesh.anchor = TextAnchor.MiddleCenter;
        textMesh.alignment = TextAlignment.Center;
        textMesh.characterSize = 0.12f;
        textMesh.fontSize = 54;
        textMesh.color = Color.white;
        textMesh.text = string.Empty;

        var font = GetLabelFont();
        if (font != null)
        {
            textMesh.font = font;
            var renderer = textMesh.GetComponent<MeshRenderer>();
            renderer.sharedMaterial = font.material;
            renderer.shadowCastingMode = ShadowCastingMode.Off;
            renderer.receiveShadows = false;
        }

        return textMesh;
    }

    private Font GetLabelFont()
    {
        if (_labelFont != null)
        {
            return _labelFont;
        }

        foreach (var name in new[] { "Arial.ttf", "LegacyRuntime.ttf" })
        {
            var font = Resources.GetBuiltinResource<Font>(name);
            if (font != null)
            {
                _labelFont = font;
                break;
            }
        }

        return _labelFont;
    }

    private Material GetSegmentMaterial(string cameraLabel)
    {
        if (_segmentMaterials.TryGetValue(cameraLabel, out var existing))
        {
            return existing;
        }

        var color = cameraLabel switch
        {
            "C001" => new Color(0.29f, 0.88f, 0.50f, 1f),
            "C002" => new Color(0.22f, 0.74f, 0.97f, 1f),
            "C003" => new Color(0.96f, 0.45f, 0.71f, 1f),
            "C004" => new Color(0.96f, 0.62f, 0.04f, 1f),
            "C005" => new Color(0.65f, 0.54f, 0.98f, 1f),
            _ => new Color(0.65f, 0.68f, 0.75f, 1f),
        };

        var material = new Material(FindShader(LineShaderCandidates))
        {
            color = color
        };
        _segmentMaterials[cameraLabel] = material;
        return material;
    }

    private Material CreateSurfaceMaterial(Color color)
    {
        var material = new Material(FindShader(SurfaceShaderCandidates))
        {
            color = color
        };

        return material;
    }

    private Shader FindShader(string[] candidates)
    {
        foreach (var shaderName in candidates)
        {
            var shader = Shader.Find(shaderName);
            if (shader != null)
            {
                return shader;
            }
        }

        Debug.LogWarning(
            "No supported shader found. Falling back to Legacy Shaders/Diffuse."
        );
        return Shader.Find("Legacy Shaders/Diffuse");
    }

    private void ClearJourneyVisuals()
    {
        foreach (var visual in _journeyVisuals)
        {
            if (visual != null)
            {
                Destroy(visual);
            }
        }

        _journeyVisuals.Clear();
    }

    private void HandleVehiclePointerInteraction()
    {
        if (_mainCamera == null)
        {
            return;
        }

        var ray = _mainCamera.ScreenPointToRay(Input.mousePosition);
        if (Physics.Raycast(ray, out var hit, 1000f))
        {
            var marker = hit.collider.GetComponentInParent<MomtVehicleMarker>();
            if (marker != _hoveredMarker)
            {
                SetHoveredMarker(marker);
            }

            if (marker != null && Input.GetMouseButtonDown(0))
            {
                SendVehicleEvent("click", marker);
            }
        }
        else if (_hoveredMarker != null)
        {
            SetHoveredMarker(null);
        }
    }

    private void SetHoveredMarker(MomtVehicleMarker marker)
    {
        if (_hoveredMarker != null)
        {
            var previous = _hoveredMarker;
            previous.SetHovered(false);
            RefreshVehiclePresentation(previous.GlobalId);
        }

        _hoveredMarker = marker;

        if (_hoveredMarker != null)
        {
            _hoveredMarker.SetHovered(true);
            RefreshVehiclePresentation(_hoveredMarker.GlobalId);
            SendVehicleEvent("hover", _hoveredMarker);
        }
        else
        {
            MomtUnity_OnVehicleEvent("{\"eventType\":\"leave\",\"globalId\":0}");
        }
    }

    private void RefreshVehiclePresentation(int globalId)
    {
        if (_liveVehicles.TryGetValue(globalId, out var visual))
        {
            ApplyVehiclePresentation(visual);
        }
    }

    private void SendVehicleEvent(string eventType, MomtVehicleMarker marker)
    {
        var payload = new VehicleEventPayload
        {
            eventType = eventType,
            globalId = marker.GlobalId,
            cameraStateLabel = marker.CameraStateLabel,
            hasCameraChanged = marker.HasCameraChanged,
            vehicleClass = marker.VehicleClass,
        };
        MomtUnity_OnVehicleEvent(JsonUtility.ToJson(payload));
    }

    private sealed class VehicleVisual
    {
        public GameObject Root;
        public MeshRenderer Renderer;
        public MomtVehicleMarker Marker;
        public BoxCollider HitCollider;
        public GameObject Symbol;
        public MeshRenderer[] SymbolRenderers;
        public TextMesh LabelText;
        public GameObject Halo;
        public MeshRenderer HaloRenderer;
        public Transform DirectionIndicator;
        public MeshRenderer DirectionIndicatorRenderer;
        public string ClassKey;
        public Color AccentColor;
        public float LastSeen;
    }
}

public sealed class MomtVehicleMarker : MonoBehaviour
{
    public int GlobalId { get; set; }
    public string CameraStateLabel { get; set; }
    public bool HasCameraChanged { get; set; }
    public string VehicleClass { get; set; }
    public bool IsHovered { get; private set; }
    public bool IsSelected { get; private set; }

    public void SetHovered(bool hovered)
    {
        IsHovered = hovered;
    }

    public void SetSelected(bool selected)
    {
        IsSelected = selected;
    }
}

public sealed class MomtBillboardText : MonoBehaviour
{
    private Camera _cachedCamera;

    private void LateUpdate()
    {
        if (_cachedCamera == null)
        {
            _cachedCamera = Camera.main;
        }

        if (_cachedCamera == null)
        {
            return;
        }

        transform.LookAt(
            transform.position + _cachedCamera.transform.rotation * Vector3.forward,
            _cachedCamera.transform.rotation * Vector3.up
        );
    }
}

[Serializable]
public sealed class DashboardStatePayload
{
    public string viewMode;
    public float timestamp;
    public int selectedGlobalId;
    public string mapTextureUrl;
    public LiveVehiclePayload[] liveVehicles;
    public JourneyPayload selectedJourney;
}

[Serializable]
public sealed class LiveVehiclePayload
{
    public int globalId;
    public string className;
    public float[] footprint;
    public float[] centroid;
    public string camera;
    public string cameraStateLabel;
    public bool hasCameraChanged;
}

[Serializable]
public sealed class JourneyPayload
{
    public int globalId;
    public string currentCameraLabel;
    public int transitionCount;
    public bool hasCameraChanged;
    public JourneyPointPayload[] pathPoints;
    public JourneySegmentPayload[] segments;
    public JourneyTransitionPayload[] transitions;
}

[Serializable]
public sealed class JourneyPointPayload
{
    public float timestamp;
    public float[] centroid;
    public float[] footprint;
    public float headingDeg;
    public string cameraLabel;
    public string className;
}

[Serializable]
public sealed class JourneySegmentPayload
{
    public string cameraLabel;
    public JourneyPointPayload[] points;
}

[Serializable]
public sealed class JourneyTransitionPayload
{
    public float timestamp;
    public float[] centroid;
    public string fromCameraLabel;
    public string toCameraLabel;
}

[Serializable]
public sealed class VehicleEventPayload
{
    public string eventType;
    public int globalId;
    public string cameraStateLabel;
    public bool hasCameraChanged;
    public string vehicleClass;
}
