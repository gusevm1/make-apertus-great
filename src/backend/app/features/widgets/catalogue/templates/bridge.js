(function () {
  // Tells the page around the widget what was clicked, how tall the widget is and what failed.
  function post(message) {
    if (window.parent !== window) window.parent.postMessage(Object.assign({ source: "trustroom-widget" }, message), "*");
  }

  function parse(text) {
    if (text === null || text === "") return null;
    try {
      return JSON.parse(text);
    } catch (error) {
      return text;
    }
  }

  function select(element, extra) {
    document.querySelectorAll("[data-selected]").forEach(function (other) { other.removeAttribute("data-selected"); });
    element.setAttribute("data-selected", "true");
    post(Object.assign({
      type: "widget-select",
      component: element.getAttribute("data-component"),
      path: element.getAttribute("data-path"),
      value: parse(element.getAttribute("data-value")),
      values: parse(element.getAttribute("data-values")),
      booking_ids: parse(element.getAttribute("data-booking-ids")) || [],
    }, extra || {}));
  }

  document.addEventListener("click", function (event) {
    // A live chart reports its own clicks, with the clicked row's values.
    if (event.target.closest("[data-live]") !== null) return;
    var mark = event.target.closest("[role='graphics-symbol'][aria-label]");
    var element = event.target.closest("[data-path]");
    if (element === null) return;
    // A mark in a static chart carries its row's path as its label.
    if (mark !== null && element.contains(mark)) {
      select(element, { path: mark.getAttribute("aria-label").replace(/^.*?:\s*/, "") });
      return;
    }
    select(element);
  });

  window.addEventListener("error", function (event) { post({ type: "widget-error", message: String(event.message) }); });

  function height() { post({ type: "widget-height", height: document.documentElement.scrollHeight }); }
  window.addEventListener("load", height);
  if (window.ResizeObserver !== undefined) new ResizeObserver(height).observe(document.body);

  // Live charts: our specs, drawn by the bundled Vega runtime.
  window.trustroomCharts = function (payload) {
    payload.charts.forEach(function (chart) {
      var host = document.getElementById(chart.id);
      host.setAttribute("data-live", "true");
      window.vegaEmbed(host, chart.spec, {
        renderer: "svg",
        actions: false,
        config: payload.config,
        formatLocale: payload.locale,
      }).then(function (result) {
        result.view.addEventListener("click", function (event, item) {
          if (item === null || item === undefined || item.datum === undefined || item.datum.path === undefined) return;
          select(host.closest("[data-path]"), {
            path: item.datum.path,
            label: item.datum.label,
            value: item.datum.y,
            booking_ids: item.datum.booking_ids,
          });
        });
        height();
      }).catch(function (error) {
        post({ type: "widget-error", message: String(error) });
      });
    });
  };
})();
