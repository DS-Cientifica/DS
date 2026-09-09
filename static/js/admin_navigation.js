(function () {
  "use strict";

  var script = document.currentScript;
  var centralUrl = script ? script.dataset.centralUrl : "/";
  var adminIndexUrl = script ? script.dataset.adminIndexUrl : "/admin/";

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".breadcrumbs a").forEach(function (link) {
      if (link.getAttribute("href") === adminIndexUrl) {
        link.setAttribute("href", centralUrl);
      }
    });
  });
})();
