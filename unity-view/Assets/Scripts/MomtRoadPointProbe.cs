using UnityEngine;

public sealed class MomtRoadPointProbe : MonoBehaviour
{
    private const float GroundPlaneHeight = 0f;

    private Camera _mainCamera;

    private void Update()
    {
        if (!IsProbeClick())
        {
            return;
        }

        if (_mainCamera == null)
        {
            _mainCamera = Camera.main;
        }

        if (_mainCamera == null)
        {
            Debug.LogWarning("[RoadPointProbe] Main camera not found.");
            return;
        }

        var ray = _mainCamera.ScreenPointToRay(Input.mousePosition);
        var plane = new Plane(Vector3.up, new Vector3(0f, GroundPlaneHeight, 0f));
        if (!plane.Raycast(ray, out var distance))
        {
            return;
        }

        var world = ray.GetPoint(distance);
        var northing = world.x + MomtCoordinateMapper.OriginNorthing;
        var easting = world.z + MomtCoordinateMapper.OriginEasting;

        Debug.Log(
            "[RoadPointProbe] " +
            $"world=({world.x:0.###}, {world.y:0.###}, {world.z:0.###}) " +
            $"P({northing:0.###}f, {easting:0.###}f)"
        );
    }

    public static bool IsProbeClick()
    {
        return Input.GetMouseButtonDown(0) &&
            (Input.GetKey(KeyCode.LeftControl) || Input.GetKey(KeyCode.RightControl));
    }

    public static bool IsProbeGestureActive()
    {
        return Input.GetMouseButton(0) &&
            (Input.GetKey(KeyCode.LeftControl) || Input.GetKey(KeyCode.RightControl));
    }
}
