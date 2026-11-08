// Apply the saved theme before the first paint (no light flash at night). Kept in a file of
// its own so the Content-Security-Policy can forbid inline scripts.
try {
  var t = localStorage.getItem("knifeforge_theme");
  if (t === "dark" || ((!t || t === "system") && matchMedia("(prefers-color-scheme: dark)").matches)) {
    document.documentElement.classList.add("dark");
  }
} catch (e) {
  /* storage blocked: light theme */
}
