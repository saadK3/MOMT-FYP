using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

public static class MomtRoadMeshBuilder
{
    public const float RoadSurfaceHeight = 0.055f;
    public const float IntersectionSurfaceHeight = 0.06f;
    public const float CurbSurfaceHeight = 0.22f;
    public const float CurbWidth = 1.2f;
    public const float LaneMarkingHeight = 0.035f;

    private static readonly Color AsphaltColor = new Color(0.24f, 0.25f, 0.25f, 1f);
    private static readonly Color CurbColor = new Color(0.68f, 0.69f, 0.66f, 1f);
    private static readonly Color LaneMarkingColor = new Color(0.86f, 0.84f, 0.76f, 1f);

    private static readonly string[] SurfaceShaderCandidates =
    {
        "Legacy Shaders/Diffuse",
        "Legacy Shaders/VertexLit",
        "Standard",
    };

    public static GameObject CreateRoadLayer()
    {
        var existing = GameObject.Find("RoadEnvironment");
        if (existing != null)
        {
            if (Application.isPlaying)
            {
                UnityEngine.Object.Destroy(existing);
            }
            else
            {
                UnityEngine.Object.DestroyImmediate(existing);
            }
        }

        var root = new GameObject("RoadEnvironment");
        var roadsParent = CreateChild(root.transform, "RoadMeshes");
        var laneParent = CreateChild(root.transform, "LaneMarkings");
        CreateChild(root.transform, "OptionalEnvironmentProps");

        var asphaltMaterial = CreateMaterial(AsphaltColor);
        var curbMaterial = CreateMaterial(CurbColor);
        var laneMaterial = CreateMaterial(LaneMarkingColor);

        BuildAuthoredRoadLayout(
            roadsParent.transform,
            laneParent.transform,
            asphaltMaterial,
            curbMaterial,
            laneMaterial
        );
        return root;
    }

    private static void BuildAuthoredRoadLayout(
        Transform roadsParent,
        Transform laneParent,
        Material asphaltMaterial,
        Material curbMaterial,
        Material laneMaterial
    )
    {
        // Road definitions are intentionally empty until centerlines are traced
        // against the fixed orthomosaic inside Unity.
        var roadPaths = new[]
        {
            new RoadPathSpec(
                "ArrowRoad_LeftSide_Test",
                7.5f,
                new[]
                {
                    P(4252583f, -9072379f),
                    P(4252604f, -9072405f),
                    P(4252621f, -9072431f),
                }
            ),
            new RoadPathSpec(
                "LeftVerticalRoad_Test",
                8.5f,
                new[]
                {
                    P(4252531f, -9072436f),
                    P(4252540f, -9072410f),
                    P(4252554f, -9072365f),
                }
            ),
            new RoadPathSpec(
                "RightVerticalRoad_Test",
                8.5f,
                new[]
                {
                    P(4252544f, -9072439f),
                    P(4252554f, -9072405f),
                    P(4252564f, -9072373f),
                }
            ),
            new RoadPathSpec(
                "UpperLeftRoad_Test",
                8.5f,
                new[]
                {
                    P(4252574f, -9072339f),
                    P(4252583f, -9072316f),
                    P(4252591f, -9072291f),
                }
            ),
            new RoadPathSpec(
                "UpperRightRoad_Test",
                8.5f,
                new[]
                {
                    P(4252562f, -9072332f),
                    P(4252570f, -9072308f),
                    P(4252576f, -9072291f),
                }
            ),
            new RoadPathSpec(
                "BottomLeftRoad_LeftSide_Test",
                8.5f,
                new[]
                {
                    P(4252524f, -9072317f),
                    P(4252537f, -9072326f),
                    P(4252551f, -9072335f),
                }
            ),
            new RoadPathSpec(
                "BottomLeftRoad_RightSide_Test",
                8.5f,
                new[]
                {
                    P(4252524f, -9072328f),
                    P(4252534f, -9072334f),
                    P(4252546f, -9072343f),
                }
            ),
        };
        var intersections = Array.Empty<IntersectionSpec>();
        var intersectionPolygons = Array.Empty<PolygonSpec>();
        var laneMarkings = Array.Empty<LaneMarkingSpec>();

        foreach (var path in roadPaths)
        {
            CreateRoadRibbon(
                roadsParent,
                path.Name,
                path.WorldPoints,
                path.WidthMeters,
                RoadSurfaceHeight,
                asphaltMaterial
            );
            CreateRoadCurbs(roadsParent, path, curbMaterial);
        }

        foreach (var intersection in intersections)
        {
            CreateIntersectionSlab(
                roadsParent,
                intersection.Name,
                intersection.Center,
                intersection.Size,
                intersection.YawDegrees,
                RoadSurfaceHeight,
                asphaltMaterial
            );
        }

        foreach (var polygon in intersectionPolygons)
        {
            CreatePolygonSlab(
                roadsParent,
                polygon.Name,
                polygon.WorldPoints,
                IntersectionSurfaceHeight,
                asphaltMaterial
            );
        }

        foreach (var lane in laneMarkings)
        {
            CreateRoadRibbon(
                laneParent,
                lane.Name,
                lane.WorldPoints,
                lane.WidthMeters,
                LaneMarkingHeight,
                laneMaterial
            );
        }
    }

    private static GameObject CreateRoadRibbon(
        Transform parent,
        string objectName,
        Vector3[] worldPoints,
        float widthMeters,
        float height,
        Material material
    )
    {
        if (worldPoints == null || worldPoints.Length < 2)
        {
            return null;
        }

        var meshObject = new GameObject(objectName);
        meshObject.transform.SetParent(parent, false);

        var meshFilter = meshObject.AddComponent<MeshFilter>();
        meshFilter.sharedMesh = CreateRibbonMesh(objectName, worldPoints, widthMeters, height);

        var meshRenderer = meshObject.AddComponent<MeshRenderer>();
        meshRenderer.material = material;
        meshRenderer.shadowCastingMode = ShadowCastingMode.Off;
        meshRenderer.receiveShadows = false;

        return meshObject;
    }

    private static void CreateRoadCurbs(
        Transform parent,
        RoadPathSpec path,
        Material curbMaterial
    )
    {
        if (path.WorldPoints == null || path.WorldPoints.Length < 2)
        {
            return;
        }

        var halfRoad = Mathf.Max(0.05f, path.WidthMeters) * 0.5f;
        var curbOffset = halfRoad + (CurbWidth * 0.5f);

        CreateRoadRibbon(
            parent,
            $"{path.Name}_CurbLeft",
            OffsetPath(path.WorldPoints, -curbOffset),
            CurbWidth,
            CurbSurfaceHeight,
            curbMaterial
        );
        CreateRoadRibbon(
            parent,
            $"{path.Name}_CurbRight",
            OffsetPath(path.WorldPoints, curbOffset),
            CurbWidth,
            CurbSurfaceHeight,
            curbMaterial
        );
    }

    private static Mesh CreateRibbonMesh(
        string meshName,
        Vector3[] worldPoints,
        float widthMeters,
        float height
    )
    {
        var halfWidth = Mathf.Max(0.05f, widthMeters) * 0.5f;
        const float baseHeight = 0f;
        var vertices = new List<Vector3>();
        var triangles = new List<int>();
        var uvs = new List<Vector2>();
        var distanceAlongPath = 0f;

        for (var index = 0; index < worldPoints.Length; index += 1)
        {
            var point = worldPoints[index];
            point.y = height;

            var tangent = GetPathTangent(worldPoints, index);
            var normal = new Vector3(-tangent.z, 0f, tangent.x).normalized;

            var leftTop = point - normal * halfWidth;
            var rightTop = point + normal * halfWidth;
            var leftBottom = new Vector3(leftTop.x, baseHeight, leftTop.z);
            var rightBottom = new Vector3(rightTop.x, baseHeight, rightTop.z);

            vertices.Add(leftTop);
            vertices.Add(rightTop);
            vertices.Add(leftBottom);
            vertices.Add(rightBottom);
            uvs.Add(new Vector2(0f, distanceAlongPath));
            uvs.Add(new Vector2(1f, distanceAlongPath));
            uvs.Add(new Vector2(0f, distanceAlongPath));
            uvs.Add(new Vector2(1f, distanceAlongPath));

            if (index < worldPoints.Length - 1)
            {
                distanceAlongPath += Vector3.Distance(worldPoints[index], worldPoints[index + 1]);
            }
        }

        for (var index = 0; index < worldPoints.Length - 1; index += 1)
        {
            var current = index * 4;
            var next = (index + 1) * 4;

            triangles.Add(current);
            triangles.Add(next);
            triangles.Add(current + 1);
            triangles.Add(current + 1);
            triangles.Add(next);
            triangles.Add(next + 1);

            triangles.Add(current + 2);
            triangles.Add(current);
            triangles.Add(next + 2);
            triangles.Add(next + 2);
            triangles.Add(current);
            triangles.Add(next);

            triangles.Add(current + 1);
            triangles.Add(current + 3);
            triangles.Add(next + 1);
            triangles.Add(next + 1);
            triangles.Add(current + 3);
            triangles.Add(next + 3);
        }

        AddRibbonEndCap(triangles, 0, false);
        AddRibbonEndCap(triangles, (worldPoints.Length - 1) * 4, true);

        var mesh = new Mesh
        {
            name = meshName
        };
        mesh.SetVertices(vertices);
        mesh.SetTriangles(triangles, 0);
        mesh.SetUVs(0, uvs);
        mesh.RecalculateNormals();
        mesh.RecalculateBounds();
        return mesh;
    }

    private static void AddRibbonEndCap(List<int> triangles, int vertexIndex, bool reverse)
    {
        if (reverse)
        {
            triangles.Add(vertexIndex);
            triangles.Add(vertexIndex + 2);
            triangles.Add(vertexIndex + 1);
            triangles.Add(vertexIndex + 1);
            triangles.Add(vertexIndex + 2);
            triangles.Add(vertexIndex + 3);
            return;
        }

        triangles.Add(vertexIndex);
        triangles.Add(vertexIndex + 1);
        triangles.Add(vertexIndex + 2);
        triangles.Add(vertexIndex + 1);
        triangles.Add(vertexIndex + 3);
        triangles.Add(vertexIndex + 2);
    }

    private static GameObject CreateIntersectionSlab(
        Transform parent,
        string objectName,
        Vector3 center,
        Vector2 size,
        float yawDegrees,
        float height,
        Material material
    )
    {
        var meshObject = new GameObject(objectName);
        meshObject.transform.SetParent(parent, false);

        var meshFilter = meshObject.AddComponent<MeshFilter>();
        meshFilter.sharedMesh = CreateRectangleMesh(objectName, center, size, yawDegrees, height);

        var meshRenderer = meshObject.AddComponent<MeshRenderer>();
        meshRenderer.material = material;
        meshRenderer.shadowCastingMode = ShadowCastingMode.Off;
        meshRenderer.receiveShadows = false;

        return meshObject;
    }

    private static GameObject CreatePolygonSlab(
        Transform parent,
        string objectName,
        Vector3[] worldPoints,
        float height,
        Material material
    )
    {
        if (worldPoints == null || worldPoints.Length < 3)
        {
            return null;
        }

        var meshObject = new GameObject(objectName);
        meshObject.transform.SetParent(parent, false);

        var meshFilter = meshObject.AddComponent<MeshFilter>();
        meshFilter.sharedMesh = CreatePolygonMesh(objectName, worldPoints, height);

        var meshRenderer = meshObject.AddComponent<MeshRenderer>();
        meshRenderer.material = material;
        meshRenderer.shadowCastingMode = ShadowCastingMode.Off;
        meshRenderer.receiveShadows = false;

        return meshObject;
    }

    private static Mesh CreatePolygonMesh(string meshName, Vector3[] worldPoints, float height)
    {
        const float baseHeight = 0f;
        var vertices = new Vector3[worldPoints.Length * 2];
        var uvs = new Vector2[worldPoints.Length * 2];
        var triangles = new List<int>();

        for (var index = 0; index < worldPoints.Length; index += 1)
        {
            vertices[index] = new Vector3(
                worldPoints[index].x,
                height,
                worldPoints[index].z
            );
            vertices[index + worldPoints.Length] = new Vector3(
                worldPoints[index].x,
                baseHeight,
                worldPoints[index].z
            );
            uvs[index] = new Vector2(worldPoints[index].x, worldPoints[index].z);
            uvs[index + worldPoints.Length] = uvs[index];
        }

        for (var index = 1; index < worldPoints.Length - 1; index += 1)
        {
            triangles.Add(0);
            triangles.Add(index);
            triangles.Add(index + 1);
        }

        for (var index = 0; index < worldPoints.Length; index += 1)
        {
            var next = (index + 1) % worldPoints.Length;
            var topCurrent = index;
            var topNext = next;
            var bottomCurrent = index + worldPoints.Length;
            var bottomNext = next + worldPoints.Length;

            triangles.Add(topCurrent);
            triangles.Add(bottomCurrent);
            triangles.Add(topNext);
            triangles.Add(topNext);
            triangles.Add(bottomCurrent);
            triangles.Add(bottomNext);
        }

        var mesh = new Mesh
        {
            name = meshName
        };
        mesh.SetVertices(vertices);
        mesh.SetTriangles(triangles, 0);
        mesh.SetUVs(0, uvs);
        mesh.RecalculateNormals();
        mesh.RecalculateBounds();
        return mesh;
    }

    private static Mesh CreateRectangleMesh(
        string meshName,
        Vector3 center,
        Vector2 size,
        float yawDegrees,
        float height
    )
    {
        center.y = height;
        var rotation = Quaternion.Euler(0f, yawDegrees, 0f);
        var halfX = Mathf.Max(0.05f, size.x) * 0.5f;
        var halfZ = Mathf.Max(0.05f, size.y) * 0.5f;

        var vertices = new[]
        {
            center + rotation * new Vector3(-halfX, 0f, -halfZ),
            center + rotation * new Vector3(halfX, 0f, -halfZ),
            center + rotation * new Vector3(-halfX, 0f, halfZ),
            center + rotation * new Vector3(halfX, 0f, halfZ),
        };

        var mesh = new Mesh
        {
            name = meshName,
            vertices = vertices,
            uv = new[]
            {
                new Vector2(0f, 0f),
                new Vector2(1f, 0f),
                new Vector2(0f, 1f),
                new Vector2(1f, 1f),
            },
            triangles = new[]
            {
                0, 2, 1,
                2, 3, 1,
            },
        };
        mesh.RecalculateNormals();
        mesh.RecalculateBounds();
        return mesh;
    }

    private static Vector3 GetPathTangent(Vector3[] points, int index)
    {
        Vector3 tangent;
        if (index == 0)
        {
            tangent = points[1] - points[0];
        }
        else if (index == points.Length - 1)
        {
            tangent = points[index] - points[index - 1];
        }
        else
        {
            tangent = points[index + 1] - points[index - 1];
        }

        tangent.y = 0f;
        return tangent.sqrMagnitude < 0.0001f ? Vector3.forward : tangent.normalized;
    }

    private static Vector3[] OffsetPath(Vector3[] points, float offset)
    {
        var offsetPoints = new Vector3[points.Length];
        for (var index = 0; index < points.Length; index += 1)
        {
            var tangent = GetPathTangent(points, index);
            var normal = new Vector3(-tangent.z, 0f, tangent.x).normalized;
            offsetPoints[index] = points[index] + normal * offset;
        }

        return offsetPoints;
    }

    private static Vector3 P(float northing, float easting)
    {
        return MomtCoordinateMapper.DataPointToWorld(northing, easting);
    }

    private static GameObject CreateChild(Transform parent, string objectName)
    {
        var child = new GameObject(objectName);
        child.transform.SetParent(parent, false);
        return child;
    }

    private static Material CreateMaterial(Color color)
    {
        return new Material(FindShader(SurfaceShaderCandidates))
        {
            color = color
        };
    }

    private static Shader FindShader(string[] candidates)
    {
        foreach (var shaderName in candidates)
        {
            var shader = Shader.Find(shaderName);
            if (shader != null)
            {
                return shader;
            }
        }

        return Shader.Find("Legacy Shaders/Diffuse");
    }

    private readonly struct RoadPathSpec
    {
        public RoadPathSpec(string name, float widthMeters, Vector3[] worldPoints)
        {
            Name = name;
            WidthMeters = widthMeters;
            WorldPoints = worldPoints;
        }

        public string Name { get; }
        public float WidthMeters { get; }
        public Vector3[] WorldPoints { get; }
    }

    private readonly struct IntersectionSpec
    {
        public IntersectionSpec(string name, Vector3 center, Vector2 size, float yawDegrees)
        {
            Name = name;
            Center = center;
            Size = size;
            YawDegrees = yawDegrees;
        }

        public string Name { get; }
        public Vector3 Center { get; }
        public Vector2 Size { get; }
        public float YawDegrees { get; }
    }

    private readonly struct PolygonSpec
    {
        public PolygonSpec(string name, Vector3[] worldPoints)
        {
            Name = name;
            WorldPoints = worldPoints;
        }

        public string Name { get; }
        public Vector3[] WorldPoints { get; }
    }

    private readonly struct LaneMarkingSpec
    {
        public LaneMarkingSpec(string name, float widthMeters, Vector3[] worldPoints)
        {
            Name = name;
            WidthMeters = widthMeters;
            WorldPoints = worldPoints;
        }

        public string Name { get; }
        public float WidthMeters { get; }
        public Vector3[] WorldPoints { get; }
    }
}
