const UNITY_HOST_URL = "/unity-host/index.html";

export class UnityEmbed {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.iframe = null;
    this.isReady = false;
    this.lastState = null;
    this.onVehicleClick = null;
    this.handleWindowMessage = this.handleWindowMessage.bind(this);
  }

  init() {
    if (!this.container || this.iframe) return;

    this.iframe = document.createElement("iframe");
    this.iframe.src = UNITY_HOST_URL;
    this.iframe.className = "unity-embed-frame";
    this.iframe.title = "MOMT Unity 3D View";
    this.iframe.allow = "fullscreen";
    this.iframe.addEventListener("load", () => {
      this.isReady = false;
    });
    this.container.appendChild(this.iframe);
    window.addEventListener("message", this.handleWindowMessage);
  }

  show() {
    this.init();
    this.container?.classList.remove("hidden");
  }

  hide() {
    this.container?.classList.add("hidden");
  }

  setState(payload) {
    this.lastState = payload;
    this.flushState();
  }

  dispose() {
    window.removeEventListener("message", this.handleWindowMessage);
  }

  handleWindowMessage(event) {
    if (event.origin !== window.location.origin) return;
    if (event.source !== this.iframe?.contentWindow) return;

    if (event.data?.type === "unity_ready") {
      this.isReady = true;
      this.flushState();
      return;
    }

    if (event.data?.type === "unity_vehicle_click") {
      const globalId = Number(event.data.globalId);
      if (Number.isInteger(globalId) && this.onVehicleClick) {
        this.onVehicleClick(globalId);
      }
    }
  }

  flushState() {
    if (!this.isReady || !this.iframe?.contentWindow || !this.lastState) return;

    this.iframe.contentWindow.postMessage(
      {
        type: "dashboard_state",
        payload: this.lastState,
      },
      window.location.origin,
    );
  }
}
