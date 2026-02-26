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

  function buildSearchIndex() {
    var main = document.querySelector("main");
    if (!main) {
      return [];
    }

    var index = [];
    var searchCounter = 0;

    function slugify(value) {
      return (value || "item")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "")
        .replace(/-+/g, "-")
        .slice(0, 90) || "search-item";
    }

    function ensureId(node, fallbackPrefix) {
      if (node.id) {
        return node.id;
      }
      var generated = fallbackPrefix + "-" + slugify(node.textContent) + "-" + searchCounter;
      searchCounter += 1;
      node.id = generated;
      return generated;
    }

    ["h2", "h3"].forEach(function (selector) {
      var headings = main.querySelectorAll(selector);
      headings.forEach(function (node) {
        var title = (node.textContent || "").trim();
        if (!title) {
          return;
        }
        var id = ensureId(node, "section");
        index.push({
          label: title,
          target: "#" + id,
          type: selector.toUpperCase()
        });
      });
    });

    var cards = main.querySelectorAll(".page-card");
    cards.forEach(function (card) {
      var labelNode = card.querySelector("h3, p");
      var label = labelNode ? (labelNode.textContent || "").trim() : "";
      if (!label) {
        return;
      }
      var href = card.getAttribute("href") || "";
      index.push({
        label: label,
        target: href,
        type: "Page Link"
      });
    });

    return index;
  }

  function initSearch() {
    var picker = document.querySelector(".theme-picker");
    if (!picker) {
      return;
    }

    var index = buildSearchIndex();
    if (!index.length) {
      return;
    }

    var searchWrap = document.createElement("label");
    searchWrap.className = "doc-search-wrap";
    searchWrap.textContent = "Search this page";

    var input = document.createElement("input");
    input.className = "doc-search-input";
    input.type = "search";
    input.placeholder = "Type to find sections and links...";
    input.setAttribute("aria-label", "Search this page");
    searchWrap.appendChild(input);

    var results = document.createElement("output");
    results.className = "doc-search-results";
    results.setAttribute("role", "listbox");
    results.hidden = true;
    picker.appendChild(searchWrap);
    picker.appendChild(results);

    function hideResults() {
      results.hidden = true;
      results.innerHTML = "";
    }

    function renderResults(query) {
      var q = (query || "").trim().toLowerCase();
      if (q.length < 2) {
        hideResults();
        return;
      }

      var matches = index.filter(function (entry) {
        return entry.label.toLowerCase().indexOf(q) !== -1;
      });

      results.innerHTML = "";
      if (!matches.length) {
        var empty = document.createElement("div");
        empty.className = "doc-search-empty";
        empty.textContent = "No matches";
        results.appendChild(empty);
        results.hidden = false;
        return;
      }

      matches.slice(0, 20).forEach(function (entry) {
        var item = document.createElement("button");
        item.type = "button";
        item.className = "doc-search-result";
        item.setAttribute("role", "option");
        item.innerHTML = "<span>" + entry.label + "</span><small>" + entry.type + "</small>";
        item.addEventListener("click", function () {
          input.value = "";
          hideResults();
          if (!entry.target) {
            return;
          }
          if (entry.target.charAt(0) === "#") {
            var targetNode = document.querySelector(entry.target);
            if (targetNode) {
              targetNode.scrollIntoView({ behavior: "smooth", block: "start" });
            }
            return;
          }
          if (entry.target.indexOf(".html") !== -1 || entry.target.indexOf("http") === 0) {
            window.location.href = entry.target;
            return;
          }
          var hashPos = entry.target.indexOf("#");
          if (hashPos > -1) {
            var file = entry.target.substring(0, hashPos);
            var hash = entry.target.substring(hashPos);
            if (!file || file === window.location.pathname.split("/").pop()) {
              window.location.hash = hash;
              return;
            }
          }
          if (entry.target.charAt(0) !== "#") {
            window.location.href = entry.target;
          }
        });
        results.appendChild(item);
      });
      results.hidden = false;
    }

    input.addEventListener("input", function () {
      renderResults(input.value);
    });

    input.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        hideResults();
        input.blur();
      }
    });

    input.addEventListener("blur", function () {
      window.setTimeout(hideResults, 150);
    });
  }

  initDynamicChrome();
  initAnchorLinks();
  initSearch();
})();
