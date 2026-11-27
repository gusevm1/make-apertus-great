(function () {
  // Collects what the benchmark checks and writes it into the page for headless Chrome to read.
  var errors = [];
  window.addEventListener("error", function (event) {
    errors.push(String(event.message || event.type) + (event.lineno ? " (line " + event.lineno + ")" : ""));
  }, true);
  window.addEventListener("unhandledrejection", function (event) {
    errors.push("unhandled rejection: " + String(event.reason));
  });
  document.addEventListener("securitypolicyviolation", function (event) {
    errors.push("blocked by the CSP: " + event.blockedURI + " (" + event.violatedDirective + ")");
  });

  function visibleTexts() {
    var texts = [];
    var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode: function (node) {
        var parent = node.parentElement;
        // Axis ticks are scale labels, not figures from the data (Vega puts them in .role-axis).
        if (parent === null || parent.closest("script, style, noscript, template, title, .tick, .axis, .role-axis")) {
          return NodeFilter.FILTER_REJECT;
        }
        return node.nodeValue.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      },
    });
    while (walker.nextNode()) texts.push(walker.currentNode.nodeValue.trim());
    return texts;
  }

  function report() {
    var body = document.body;
    var root = document.documentElement;
    var result = {
      errors: errors,
      texts: body ? visibleTexts() : [],
      drawn: !!body && (body.innerText.trim().length > 0 || !!body.querySelector("svg *, canvas, img")),
      uses_canvas: !!document.querySelector("canvas"),
      height: root.scrollHeight,
      overflows: root.scrollWidth > root.clientWidth + 1,
    };
    var element = document.createElement("script");
    element.type = "application/json";
    element.id = "bench-report";
    element.textContent = JSON.stringify(result).replace(/</g, "\\u003c");
    root.appendChild(element);
  }

  // Time for the widget's own timers and transitions; VIRTUAL_TIME_MS in run.py must exceed it.
  var REPORT_DELAY_MS = 1500;
  window.addEventListener("load", function () {
    setTimeout(report, REPORT_DELAY_MS);
  });
})();
