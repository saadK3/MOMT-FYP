# Unity Setup And Workflow

This guide explains how to set up Unity for the MOMT 3D visualization, connect it with VS Code, edit the Unity scripts, build WebGL, and run the dashboard.

## 1. Required Tools

Install these tools first:

- Unity Hub
- Unity Editor 6.3 LTS, version `6000.3.3f1`
- Visual Studio Code
- Git
- Node.js
- Python

The Unity project is located at:

```text
unity-view
```

The dashboard WebGL build output is located at:

```text
dashboard/public/unity-webgl
```

## 2. Install Unity Hub

1. Open this page in a browser:

```text
https://unity.com/download
```

2. Download **Unity Hub** for Windows.
3. Run the installer.
4. Open Unity Hub after installation.
5. Sign in with a Unity account if Unity asks for it.

## 3. Install The Correct Unity Version

This project expects:

```text
Unity 6.3 LTS
Editor version: 6000.3.3f1
```

In Unity Hub:

1. Click **Installs**.
2. Click **Install Editor**.
3. Select **Unity 6.3 LTS**.
4. Choose version `6000.3.3f1` if it is shown.
5. In modules, include:

```text
Microsoft Visual Studio Community / IDE support, optional
WebGL Build Support, required
Windows Build Support, optional
```

The important module is:

```text
WebGL Build Support
```

Without WebGL Build Support, the dashboard Unity view cannot be rebuilt.

## 4. Open The Unity Project

In Unity Hub:

1. Click **Projects**.
2. Click **Add**.
3. Select this folder:

```text
C:\Users\abdul\Desktop\MOMT-FYP\unity-view
```

4. Open the project.
5. Wait until Unity finishes importing and compiling.

If Unity shows warnings about the old Input Manager, that is okay. Red Console errors are not okay.

## 5. Open The Main Scene

In the Unity Project panel:

1. Open:

```text
Assets > Scenes
```

2. Double-click:

```text
Momt3D
```

The Hierarchy should show:

```text
DashboardBridge
Main Camera
Directional Light
```

When Play Mode starts, runtime objects are created:

```text
GroundPlane
RoadEnvironment
Vehicles
Trajectory lines
```

## 6. Generate The Scene If Needed

If the scene is empty or broken, use the MOMT menu:

```text
MOMT > Generate Unity 3D Scene
```

Then save:

```text
File > Save
```

This recreates the basic Unity scene scaffold.

## 7. Use VS Code With Unity

Most Unity code edits are done in VS Code.

Open the repository folder in VS Code:

```text
C:\Users\abdul\Desktop\MOMT-FYP
```

Important Unity scripts:

```text
unity-view/Assets/Scripts/MomtDashboardBridge.cs
unity-view/Assets/Scripts/MomtCoordinateMapper.cs
unity-view/Assets/Scripts/MomtRoadMeshBuilder.cs
unity-view/Assets/Scripts/MomtRoadPointProbe.cs
unity-view/Assets/Scripts/MomtOrbitCamera.cs
```

Recommended VS Code extensions:

- C#
- C# Dev Kit, optional
- Unity, optional

After editing C# scripts in VS Code:

1. Save the file.
2. Return to Unity.
3. Wait for Unity to compile.
4. Check the Console for red errors.

Do not edit Unity-generated `Library` files.

## 8. Current 3D Road Layer

The road visualization code is in:

```text
unity-view/Assets/Scripts/MomtRoadMeshBuilder.cs
```

It creates:

```text
RoadEnvironment
  RoadMeshes
  LaneMarkings
  OptionalEnvironmentProps
```

The mosaic is still the fixed reference layer. Do not move, rotate, or rescale it.

The coordinate mapper is:

```text
unity-view/Assets/Scripts/MomtCoordinateMapper.cs
```

Do not change the mosaic bounds or coordinate conversion unless the whole mapping is intentionally being recalibrated.

## 9. Road Point Collection In Unity

During editing, `MomtRoadPointProbe` helps collect exact map coordinates.

Use this gesture in Play Mode:

```text
Ctrl + Left Click
```

Unity Console prints a point like:

```text
[RoadPointProbe] world=(...) P(4252563f, -9072351f)
```

Copy only the `P(...)` value into `MomtRoadMeshBuilder.cs`.

Normal mouse controls:

```text
Left drag: orbit camera
Right drag: pan camera
Scroll wheel: zoom
Ctrl + left click: record coordinate point
```

## 10. Editing Roads

Road centerlines are defined as `RoadPathSpec` entries.

Example:

```csharp
new RoadPathSpec(
    "Road_Main_01",
    8.5f,
    new[]
    {
        P(4252531f, -9072436f),
        P(4252540f, -9072410f),
        P(4252554f, -9072365f),
    }
)
```

The width value is in Unity meters:

```text
5 to 7: narrow road
8 to 10: normal two-lane road
12+: wide road or broad ramp
```

## 11. Editing The Intersection

The intersection is defined as a polygon in:

```text
MomtRoadMeshBuilder.cs
```

For a custom intersection polygon, click the desired polygon corners in Unity and copy the printed `P(...)` points.

Use this order:

```text
top-left
top-right
bottom-right
bottom-left
```

The current implementation creates an extruded polygon slab so it has visible thickness.

## 12. Build Unity WebGL

After the Unity scene looks correct:

1. In Unity, open the top menu:

```text
MOMT > Build Unity WebGL
```

2. Wait for build completion.

The build output is written to:

```text
dashboard/public/unity-webgl
```

The dashboard browser view will not show new Unity changes until this WebGL build is updated.

## 13. Run The Full Project

From PowerShell:

```powershell
cd C:\Users\abdul\Desktop\MOMT-FYP
.\venv\Scripts\activate
python run_system.py
```

Open:

```text
http://localhost:3000
```

Optional frame server for video panels:

```powershell
cd C:\Users\abdul\Desktop\MOMT-FYP
.\venv\Scripts\activate
python tools\frame_server.py
```

## 14. What To Verify

In Unity and in the dashboard, verify:

- Mosaic appears correctly.
- Vehicles still align with the mosaic.
- Trajectory lines still align with the mosaic.
- Road meshes do not change the coordinate system.
- Intersection shape is acceptable.
- No red errors appear in Unity Console.
- WebGL loads in the dashboard.

## 15. Important Rules

Do not:

- Rescale the mosaic.
- Rotate the mosaic.
- Change `MomtCoordinateMapper` bounds casually.
- Change the tracking server for road visuals.
- Change vehicle coordinate mapping for road visuals.
- Use AI terrain or depth estimation.

The road layer is visual only. The orthomosaic remains the spatial ground truth.

