// Re-renders the "generated links" of the share form while the text is edited,
// so the links can be copied without saving anything.
document.addEventListener("DOMContentLoaded", () => {
  const preview = document.getElementById("share-preview");
  const text = document.getElementById("id_text");
  const url = document.getElementById("id_url");
  const csrf = document.querySelector("[name=csrfmiddlewaretoken]");
  if (!preview || !text || !url || !csrf) {
    return;
  }

  let timeout;
  let controller;

  const refresh = async () => {
    controller?.abort();
    controller = new AbortController();

    const body = new FormData();
    body.append("text", text.value);
    body.append("url", url.value);

    try {
      const response = await fetch(preview.dataset.url, {
        method: "POST",
        body,
        headers: { "X-CSRFToken": csrf.value },
        signal: controller.signal,
      });
      if (response.ok) {
        preview.innerHTML = await response.text();
      }
    } catch (error) {
      if (error.name !== "AbortError") {
        throw error;
      }
    }
  };

  const schedule = () => {
    clearTimeout(timeout);
    timeout = setTimeout(refresh, 250);
  };

  text.addEventListener("input", schedule);
  url.addEventListener("input", schedule);

  preview.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-copy]");
    if (!button) {
      return;
    }
    await navigator.clipboard.writeText(button.dataset.copy);
    const label = button.textContent;
    button.textContent = "✓";
    setTimeout(() => {
      button.textContent = label;
    }, 1200);
  });
});
