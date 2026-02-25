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
    select.value = savedTheme;
  }

  select.addEventListener("change", function (event) {
    var theme = event.target.value;
    applyTheme(theme);
    localStorage.setItem(storageKey, theme);
  });

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

  var tocLinks = document.querySelectorAll(".toc a");
  var sections = document.querySelectorAll("main section[id]");

  var observer = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) {
          return;
        }
        var id = entry.target.getAttribute("id");
        tocLinks.forEach(function (link) {
          link.classList.toggle("active", link.getAttribute("href") === "#" + id);
        });
      });
    },
    { rootMargin: "-35% 0px -55% 0px", threshold: 0.01 }
  );

  sections.forEach(function (section) {
    observer.observe(section);
  });
})();
