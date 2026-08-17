const THEME_KEY = "sonus-theme";

export function resolveInitialTheme(storedTheme) {
  return storedTheme === "dark" ? "dark" : "light";
}

export function applyTheme(root, toggle, theme) {
  const dark = theme === "dark";
  root.dataset.theme = dark ? "dark" : "light";
  toggle.setAttribute("aria-pressed", String(dark));
  toggle.setAttribute("aria-label", dark ? "라이트 테마로 전환" : "다크 테마로 전환");
}

export function toggleTheme(currentTheme, storage) {
  const nextTheme = currentTheme === "dark" ? "light" : "dark";
  storage.setItem(THEME_KEY, nextTheme);
  return nextTheme;
}

function initializePreview() {
  const root = document.documentElement;
  const themeToggle = document.querySelector("[data-theme-toggle]");

  if (themeToggle) {
    let theme = resolveInitialTheme(localStorage.getItem(THEME_KEY));
    applyTheme(root, themeToggle, theme);

    themeToggle.addEventListener("click", () => {
      theme = toggleTheme(theme, localStorage);
      applyTheme(root, themeToggle, theme);
    });
  }

  const links = [...document.querySelectorAll("[data-section-link]")];
  const sections = [...document.querySelectorAll("main section[id]")];

  if ("IntersectionObserver" in window && links.length && sections.length) {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];

        if (!visible) return;

        links.forEach((link) => {
          const active = link.getAttribute("href") === `#${visible.target.id}`;
          link.classList.toggle("is-active", active);
          if (active) link.setAttribute("aria-current", "location");
          else link.removeAttribute("aria-current");
        });
      },
      { rootMargin: "-18% 0px -68%", threshold: [0, 0.2, 0.6] },
    );

    sections.forEach((section) => observer.observe(section));
  }
}

if (typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializePreview, { once: true });
  } else {
    initializePreview();
  }
}
