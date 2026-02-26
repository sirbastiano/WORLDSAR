(function () {
  var body = document.body;
  var select = document.getElementById("theme-select");
  var storageKey = "worldsar-docs-theme";

  function applyTheme(themeClass) {
    body.classList.remove("theme-midnight", "theme-carbon", "theme-slate");
    body.classList.add(themeClass);
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(value, max));
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
      var oldLabel = button.textContent;
      button.textContent = "Copied";
      button.classList.add("copied");

      var copyPromise = null;
      if (navigator && navigator.clipboard && navigator.clipboard.writeText) {
        copyPromise = navigator.clipboard.writeText(text);
      } else {
        copyPromise = new Promise(function (resolve, reject) {
          try {
            var temp = document.createElement("textarea");
            temp.style.position = "fixed";
            temp.style.left = "-9999px";
            temp.style.top = "0";
            temp.value = text;
            body.appendChild(temp);
            temp.focus();
            temp.select();
            var ok = document.execCommand("copy");
            body.removeChild(temp);
            if (ok) {
              resolve();
            } else {
              reject(new Error("copy failed"));
            }
          } catch (err) {
            reject(err);
          }
        });
      }

      copyPromise.then(function () {
        // optimistic feedback already shown
      }, function () {
        button.textContent = "Copy error";
      }).finally(function () {
        setTimeout(function () {
          button.textContent = oldLabel;
          button.classList.remove("copied");
        }, 1100);
      });
    });
  });

  var page = (window.location.pathname.split("/").pop() || "index.html").toLowerCase();
  if (page === "index.html" || page === "") {
    page = "intro.html";
  }
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

  function initDynamicChrome() {
    var heroContent = document.querySelector(".hero-content");
    var support = document.createElement("div");
    support.className = "site-dynamic-meta";
    support.setAttribute("aria-live", "polite");

    var stamp = document.createElement("small");
    stamp.textContent = "Last modified: " + document.lastModified;
    support.appendChild(stamp);
    if (heroContent) {
      heroContent.appendChild(support);
    } else {
      body.appendChild(support);
    }

    var progress = document.createElement("div");
    progress.className = "scroll-progress";
    var bar = document.createElement("span");
    progress.appendChild(bar);
    body.appendChild(progress);

    var backToTop = document.createElement("button");
    backToTop.className = "back-to-top";
    backToTop.type = "button";
    backToTop.setAttribute("aria-label", "Back to top");
    backToTop.textContent = "↑ Top";
    backToTop.hidden = true;
    body.appendChild(backToTop);

    function updateChrome() {
      var scrollTop = window.pageYOffset || document.documentElement.scrollTop || document.body.scrollTop || 0;
      var maxScroll = Math.max(document.documentElement.scrollHeight - window.innerHeight, 1);
      var pct = clamp(Math.round((scrollTop / maxScroll) * 100), 0, 100);
      bar.style.width = pct + "%";
      backToTop.hidden = scrollTop <= 250;
    }

    window.addEventListener("scroll", updateChrome, { passive: true });
    updateChrome();

    backToTop.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });

  }

  function initAnchorLinks() {
    var anchors = document.querySelectorAll('a[href^="#"]');
    anchors.forEach(function (link) {
      link.addEventListener("click", function (event) {
        var hash = link.getAttribute("href");
        if (!hash || hash.length < 2) {
          return;
        }
        var target = document.querySelector(hash);
        if (!target) {
          return;
        }
        event.preventDefault();
        target.scrollIntoView({ behavior: "smooth", block: "start" });
        window.history.pushState({}, "", hash);
      });
    });
  }

  initDynamicChrome();
  initAnchorLinks();
})();
