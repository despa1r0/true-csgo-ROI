/** Chart colours come from the page tokens, so both themes stay consistent. */
export function chartTheme() {
  const styles = getComputedStyle(document.documentElement);
  const token = (name: string, fallback: string) => styles.getPropertyValue(name).trim() || fallback;
  return {
    line: token("--color-text-primary", "#161616"),
    axis: token("--color-text-muted", "#7c7c7c"),
    grid: token("--color-border-subtle", "#e6e6e3"),
    surface: token("--color-surface", "#ffffff"),
    border: token("--color-border-strong", "#cfcfcb"),
    text: token("--color-text-primary", "#161616"),
  };
}
