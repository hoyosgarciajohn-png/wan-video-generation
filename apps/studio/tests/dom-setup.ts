import { JSDOM } from "jsdom";
const dom = new JSDOM(
  '<!doctype html><html lang="en"><head><title>WAN Studio test</title></head><body></body></html>',
  { url: "http://localhost/" },
);
for (const key of [
  "FormData",
  "window",
  "document",
  "navigator",
  "HTMLElement",
  "HTMLInputElement",
  "HTMLDialogElement",
  "Node",
  "Event",
  "StorageEvent",
  "MutationObserver",
  "localStorage",
  "getComputedStyle",
]) {
  Object.defineProperty(globalThis, key, {
    value: (dom.window as any)[key],
    configurable: true,
  });
}
Object.assign(globalThis, {
  addEventListener: dom.window.addEventListener.bind(dom.window),
  removeEventListener: dom.window.removeEventListener.bind(dom.window),
  IS_REACT_ACT_ENVIRONMENT: true,
});
// DOM emulation supports dialog visibility only. Native focus and Escape are browser checks.
dom.window.HTMLDialogElement.prototype.showModal = function () {
  this.setAttribute("open", "");
};
dom.window.HTMLDialogElement.prototype.close = function () {
  this.removeAttribute("open");
};
