/**
 * USIS AI review lifecycle pub/sub (Plan 1 / Plan 12).
 * Modes: bid_feasibility_review, estimating_review, construction_review, etc.
 */
(function (global) {
  "use strict";

  var listeners = {};

  function aiReviewBus() {}

  aiReviewBus.prototype.on = function (eventName, handler) {
    if (!eventName || typeof handler !== "function") return function noop() {};
    if (!listeners[eventName]) listeners[eventName] = [];
    listeners[eventName].push(handler);
    return function off() {
      var arr = listeners[eventName];
      if (!arr) return;
      var i = arr.indexOf(handler);
      if (i !== -1) arr.splice(i, 1);
    };
  };

  aiReviewBus.prototype.off = function (eventName, handler) {
    var arr = listeners[eventName];
    if (!arr) return;
    if (!handler) {
      listeners[eventName] = [];
      return;
    }
    var i = arr.indexOf(handler);
    if (i !== -1) arr.splice(i, 1);
  };

  aiReviewBus.prototype.emit = function (eventName, payload) {
    var arr = listeners[eventName];
    if (!arr || !arr.length) return;
    arr.slice().forEach(function (fn) {
      try {
        fn(payload);
      } catch (e) {
        if (global.console && console.error) console.error("[aiReviewBus]", eventName, e);
      }
    });
  };

  global.aiReviewBus = new aiReviewBus();
})(typeof window !== "undefined" ? window : this);
