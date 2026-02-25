(function () {
  var body = document.body;
  var select = document.getElementById("theme-select");
  var storageKey = "worldsar-docs-theme";

  function applyTheme(themeClass) {
    body.classList.remove("theme-midnight", "theme-carbon", "theme-slate");
    body.classList.add(themeClass);
  }

  var savedTheme = localStorage.getItem(storageKey);
  if (savedTheme && savedTheme !== body.className) {
    applyTheme(savedTheme);
    if (select) {
      select.value = savedTheme;
    }
  }

  if (select) {
    select.addEventListener("change", function (event) {
      var theme = event.target.value;
      applyTheme(theme);
      localStorage.setItem(storageKey, theme);
    });
  }

  var copyButtons = document.querySelectorAll(".copy-btn");
  copyButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      var pre = button.parentElement.querySelector("pre");
      if (!pre) {
        return;
      }
      var text = pre.innerText;
      navigator.clipboard.writeText(text).then(function () {
        var oldLabel = button.textContent;
        button.textContent = "Copied";
        button.classList.add("copied");
        setTimeout(function () {
          button.textContent = oldLabel;
          button.classList.remove("copied");
        }, 1100);
      });
    });
  });

  var page = (window.location.pathname.split("/").pop() || "index.html").toLowerCase();
  var navLinks = document.querySelectorAll(".site-nav a");
  navLinks.forEach(function (link) {
    var href = link.getAttribute("href");
    if (!href) {
      return;
    }
    var target = href.replace("./", "").toLowerCase();
    if (target === page || (page === "" && target === "index.html")) {
      link.classList.add("active");
    }
  });
})();
