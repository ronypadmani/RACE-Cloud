/**
 * Lightweight cross-page event bus.
 * Pages emit events (e.g. 'recommendations-changed') and other pages
 * that are mounted can subscribe and react (e.g. refresh data).
 */
const listeners = {};

const dashboardEvents = {
  on(event, fn) {
    if (!listeners[event]) listeners[event] = [];
    listeners[event].push(fn);
  },

  off(event, fn) {
    if (!listeners[event]) return;
    listeners[event] = listeners[event].filter(f => f !== fn);
  },

  emit(event, data) {
    (listeners[event] || []).forEach(fn => fn(data));
  },
};

export default dashboardEvents;
