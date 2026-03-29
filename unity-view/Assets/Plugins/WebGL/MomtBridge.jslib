mergeInto(LibraryManager.library, {
  MomtUnity_OnReady: function () {
    if (window.MomtUnityHost && typeof window.MomtUnityHost.onReady === "function") {
      window.MomtUnityHost.onReady();
    }
  },

  MomtUnity_OnVehicleEvent: function (payloadPtr) {
    var payload = UTF8ToString(payloadPtr);
    if (
      window.MomtUnityHost &&
      typeof window.MomtUnityHost.onVehicleEvent === "function"
    ) {
      window.MomtUnityHost.onVehicleEvent(payload);
    }
  },
});
