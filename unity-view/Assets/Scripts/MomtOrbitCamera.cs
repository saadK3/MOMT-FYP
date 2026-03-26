using UnityEngine;

public sealed class MomtOrbitCamera : MonoBehaviour
{
    [SerializeField] private float distance = 130f;
    [SerializeField] private float minDistance = 20f;
    [SerializeField] private float maxDistance = 240f;
    [SerializeField] private float yaw = 28f;
    [SerializeField] private float pitch = 56f;
    [SerializeField] private float orbitSpeed = 4f;
    [SerializeField] private float panSpeed = 0.25f;
    [SerializeField] private float zoomSpeed = 12f;

    private Vector3 _target = Vector3.zero;

    public void SetTarget(Vector3 target, bool snap = false)
    {
        _target = target;
        if (snap)
        {
            UpdateCameraTransform();
        }
    }

    public void FrameBounds(Bounds bounds)
    {
        _target = bounds.center;
        var radius = Mathf.Max(bounds.extents.x, bounds.extents.z, 8f);
        distance = Mathf.Clamp(radius * 3.4f, minDistance, maxDistance);
        UpdateCameraTransform();
    }

    private void LateUpdate()
    {
        if (Input.GetMouseButton(0))
        {
            yaw += Input.GetAxis("Mouse X") * orbitSpeed;
            pitch -= Input.GetAxis("Mouse Y") * orbitSpeed;
            pitch = Mathf.Clamp(pitch, 18f, 80f);
        }

        if (Input.GetMouseButton(1))
        {
            var right = transform.right;
            var forward = Vector3.ProjectOnPlane(transform.forward, Vector3.up).normalized;
            _target -= right * Input.GetAxis("Mouse X") * panSpeed;
            _target -= forward * Input.GetAxis("Mouse Y") * panSpeed;
        }

        distance = Mathf.Clamp(
            distance - (Input.mouseScrollDelta.y * zoomSpeed),
            minDistance,
            maxDistance
        );

        UpdateCameraTransform();
    }

    private void UpdateCameraTransform()
    {
        var rotation = Quaternion.Euler(pitch, yaw, 0f);
        transform.position = _target + (rotation * new Vector3(0f, 0f, -distance));
        transform.LookAt(_target);
    }
}
