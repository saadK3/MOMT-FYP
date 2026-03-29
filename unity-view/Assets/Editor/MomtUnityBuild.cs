using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

public static class MomtUnityBuild
{
    private const string ScenePath = "Assets/Scenes/Momt3D.unity";

    [MenuItem("MOMT/Generate Unity 3D Scene")]
    public static void GenerateScene()
    {
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        var bridge = new GameObject("DashboardBridge");
        bridge.AddComponent<MomtDashboardBridge>();

        var cameraObject = new GameObject("Main Camera");
        cameraObject.tag = "MainCamera";
        var camera = cameraObject.AddComponent<Camera>();
        camera.clearFlags = CameraClearFlags.SolidColor;
        camera.backgroundColor = new Color(0.04f, 0.07f, 0.11f, 1f);
        camera.fieldOfView = 55f;
        cameraObject.AddComponent<AudioListener>();
        var orbit = cameraObject.AddComponent<MomtOrbitCamera>();
        orbit.SetTarget(Vector3.zero, true);

        var lightObject = new GameObject("Directional Light");
        var light = lightObject.AddComponent<Light>();
        light.type = LightType.Directional;
        light.color = new Color(1f, 0.96f, 0.9f, 1f);
        light.intensity = 1.25f;
        light.shadows = LightShadows.Soft;
        lightObject.transform.rotation = Quaternion.Euler(46f, -32f, 0f);

        RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat;
        RenderSettings.ambientLight = new Color(0.33f, 0.40f, 0.50f, 1f);

        EditorSceneManager.SaveScene(scene, ScenePath);
        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();
    }

    [MenuItem("MOMT/Build Unity WebGL")]
    public static void BuildWebGl()
    {
        EnsureSceneExists();
        EnsureProjectVersion();

        var projectRoot = Directory.GetParent(Application.dataPath)?.FullName
            ?? throw new InvalidOperationException("Unity project root not found.");
        var repoRoot = Directory.GetParent(projectRoot)?.FullName
            ?? throw new InvalidOperationException("Repository root not found.");
        var outputRoot = Path.Combine(repoRoot, "dashboard", "public", "unity-webgl");

        Directory.CreateDirectory(outputRoot);
        EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.WebGL, BuildTarget.WebGL);
        PlayerSettings.companyName = "MOMT";
        PlayerSettings.productName = "MOMTUnity3D";
        PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Disabled;

        var buildReport = BuildPipeline.BuildPlayer(
            new[] { ScenePath },
            outputRoot,
            BuildTarget.WebGL,
            BuildOptions.None
        );

        if (buildReport.summary.result != UnityEditor.Build.Reporting.BuildResult.Succeeded)
        {
            throw new InvalidOperationException("Unity WebGL build failed.");
        }

        WriteBuildConfig(outputRoot);
        AssetDatabase.Refresh();
    }

    private static void EnsureSceneExists()
    {
        if (!File.Exists(Path.Combine(Directory.GetParent(Application.dataPath)?.FullName ?? ".", "Assets", "Scenes", "Momt3D.unity")))
        {
            GenerateScene();
        }
    }

    private static void EnsureProjectVersion()
    {
        var projectRoot = Directory.GetParent(Application.dataPath)?.FullName;
        if (projectRoot == null)
        {
            return;
        }

        var versionPath = Path.Combine(projectRoot, "ProjectSettings", "ProjectVersion.txt");
        var versionContents =
            "m_EditorVersion: 6000.3.3f1\n" +
            "m_EditorVersionWithRevision: 6000.3.3f1 (ef04196de0d6)\n";
        File.WriteAllText(versionPath, versionContents);
    }

    private static void WriteBuildConfig(string outputRoot)
    {
        var buildDir = Path.Combine(outputRoot, "Build");
        var loaderName = Directory.GetFiles(buildDir, "*.loader.js").Select(Path.GetFileName).FirstOrDefault();
        var dataName = Directory.GetFiles(buildDir, "*.data*").Select(Path.GetFileName).FirstOrDefault();
        var frameworkName = Directory.GetFiles(buildDir, "*.framework.js*").Select(Path.GetFileName).FirstOrDefault();
        var codeName = Directory.GetFiles(buildDir, "*.wasm*").Select(Path.GetFileName).FirstOrDefault();

        var config = new UnityBuildConfig
        {
            loaderUrl = $"Build/{loaderName}",
            dataUrl = $"Build/{dataName}",
            frameworkUrl = $"Build/{frameworkName}",
            codeUrl = $"Build/{codeName}",
            companyName = PlayerSettings.companyName,
            productName = PlayerSettings.productName,
            productVersion = Application.unityVersion,
        };

        var configJson = JsonUtility.ToJson(config, true);
        File.WriteAllText(Path.Combine(outputRoot, "build-config.json"), configJson);
    }

    [Serializable]
    private sealed class UnityBuildConfig
    {
        public string loaderUrl;
        public string dataUrl;
        public string frameworkUrl;
        public string codeUrl;
        public string companyName;
        public string productName;
        public string productVersion;
    }
}
