using System;
using UnityEngine;

public static class MomtCoordinateMapper
{
    // These bounds match the 2D dashboard mosaic exactly:
    //   x-axis -> northing
    //   y-axis -> easting
    public const float MosaicNorthingMin = 4252523.5462492965f;
    public const float MosaicNorthingMax = 4252623.142834548f;
    public const float MosaicEastingMin = -9072438.675959857f;
    public const float MosaicEastingMax = -9072289.704694824f;

    public static readonly float OriginNorthing =
        (MosaicNorthingMin + MosaicNorthingMax) * 0.5f;
    public static readonly float OriginEasting =
        (MosaicEastingMin + MosaicEastingMax) * 0.5f;

    // Unity world uses:
    //   world X -> northing delta
    //   world Z -> easting delta
    public static readonly float GroundWidth =
        Mathf.Abs(MosaicNorthingMax - MosaicNorthingMin);
    public static readonly float GroundLength =
        Mathf.Abs(MosaicEastingMax - MosaicEastingMin);

    public static Vector3 CentroidToWorld(float[] centroid)
    {
        if (centroid == null || centroid.Length < 2)
        {
            return Vector3.zero;
        }

        return DataPointToWorld(centroid[0], centroid[1]);
    }

    public static Vector3 DataPointToWorld(float northing, float easting)
    {
        return new Vector3(
            northing - OriginNorthing,
            0f,
            easting - OriginEasting
        );
    }

    public static Vector3[] FootprintToWorld(float[] footprint)
    {
        if (footprint == null || footprint.Length != 8)
        {
            return Array.Empty<Vector3>();
        }

        var corners = new Vector3[4];
        for (var index = 0; index < 8; index += 2)
        {
            corners[index / 2] = DataPointToWorld(
                footprint[index],
                footprint[index + 1]
            );
        }

        return corners;
    }

    public static VehicleGeometry ComputeVehicleGeometry(float[] footprint)
    {
        var corners = FootprintToWorld(footprint);
        if (corners.Length != 4)
        {
            return new VehicleGeometry(1.8f, 4.2f, 0f);
        }

        var frontLeft = corners[0];
        var frontRight = corners[1];
        var rearLeft = corners[2];
        var rearRight = corners[3];

        var frontCenter = (frontLeft + frontRight) * 0.5f;
        var rearCenter = (rearLeft + rearRight) * 0.5f;

        var frontWidth = Vector3.Distance(frontLeft, frontRight);
        var rearWidth = Vector3.Distance(rearLeft, rearRight);
        var leftLength = Vector3.Distance(frontLeft, rearLeft);
        var rightLength = Vector3.Distance(frontRight, rearRight);

        var width = Mathf.Clamp((frontWidth + rearWidth) * 0.5f, 0.8f, 6f);
        var length = Mathf.Clamp((leftLength + rightLength) * 0.5f, 1.6f, 18f);

        var headingVector = frontCenter - rearCenter;
        headingVector.y = 0f;
        if (headingVector.sqrMagnitude < 0.0001f)
        {
            headingVector = frontRight - rearRight;
            headingVector.y = 0f;
        }

        var headingDegrees = Mathf.Atan2(headingVector.x, headingVector.z) * Mathf.Rad2Deg;
        return new VehicleGeometry(width, length, headingDegrees);
    }

    public static float HeadingDataToWorld(float headingDegrees)
    {
        return 90f - headingDegrees;
    }

    public static Mesh CreateGroundMesh()
    {
        var mesh = new Mesh
        {
            name = "MomtGroundQuad"
        };

        mesh.vertices = new[]
        {
            DataPointToWorld(MosaicNorthingMin, MosaicEastingMin),
            DataPointToWorld(MosaicNorthingMax, MosaicEastingMin),
            DataPointToWorld(MosaicNorthingMin, MosaicEastingMax),
            DataPointToWorld(MosaicNorthingMax, MosaicEastingMax),
        };

        mesh.uv = new[]
        {
            new Vector2(0f, 0f),
            new Vector2(1f, 0f),
            new Vector2(0f, 1f),
            new Vector2(1f, 1f),
        };

        mesh.triangles = new[]
        {
            0, 2, 1,
            2, 3, 1,
        };

        mesh.RecalculateNormals();
        mesh.RecalculateBounds();
        return mesh;
    }

    public static float GetVehicleHeight(string className)
    {
        return className switch
        {
            "Sedan" => 1.5f,
            "SUV / Hatchback" => 1.8f,
            "Pickup / Minitruck" => 2.2f,
            "Truck" => 3.0f,
            "Truck / Semi-Truck" => 3.4f,
            "Bus" => 3.2f,
            "Motorcycle" => 1.2f,
            "Bike" => 1.1f,
            "Van" => 2.3f,
            _ => 1.6f,
        };
    }

    public readonly struct VehicleGeometry
    {
        public VehicleGeometry(float width, float length, float headingDegrees)
        {
            Width = width;
            Length = length;
            HeadingDegrees = headingDegrees;
        }

        public float Width { get; }
        public float Length { get; }
        public float HeadingDegrees { get; }
    }
}
