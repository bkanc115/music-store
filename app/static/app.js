// Отправка форм веб-интерфейса в JSON API.
// <form data-api="/api/..." data-method="POST" [data-redirect="/path"]>
// <form data-api-template="/api/x/{field}/y">  — поле с data-path подставляется в адрес.

function formToJson(form) {
  const body = {};
  for (const el of form.elements) {
    if (!el.name || el.dataset.path) continue;
    const raw = el.value.trim();
    if (raw === "") continue; // пустое поле = значение не задано
    const type = el.dataset.type || (el.type === "number" ? "num" : "str");
    body[el.name] = type === "int" ? parseInt(raw, 10) : type === "num" ? Number(raw) : raw;
  }
  return body;
}

function formUrl(form) {
  if (form.dataset.api) return form.dataset.api;
  return form.dataset.apiTemplate.replace(/\{(\w+)\}/g, (_, name) =>
    encodeURIComponent(form.elements[name].value));
}

function errorText(data, status) {
  const err = data && data.error;
  if (!err) return `Ошибка ${status}`;
  let text = err.message;
  if (Array.isArray(err.details)) {
    text += ": " + err.details.map((d) => `${d.field} — ${d.message}`).join("; ");
  } else if (err.details && typeof err.details === "object") {
    text += " (" + Object.entries(err.details).map(([k, v]) => `${k}: ${v}`).join(", ") + ")";
  }
  return text;
}

document.querySelectorAll("form[data-api], form[data-api-template]").forEach((form) => {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const out = form.querySelector(".form-error");
    if (out) out.textContent = "";
    const response = await fetch(formUrl(form), {
      method: form.dataset.method || "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formToJson(form)),
    });
    if (response.ok) {
      window.location.href = form.dataset.redirect || window.location.href;
      return;
    }
    const data = await response.json().catch(() => null);
    if (out) out.textContent = errorText(data, response.status);
  });
});

const logout = document.getElementById("logout");
if (logout) {
  logout.addEventListener("click", async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    window.location.href = "/";
  });
}
