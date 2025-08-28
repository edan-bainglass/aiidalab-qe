export function render({ model, el }) {
  const a = document.createElement("a");

  function buildContents() {
    a.replaceChildren();
    const icon = model.get("icon") || "";
    if (icon) {
      const i = document.createElement("i");
      i.className = `fa fa-${icon}`;
      i.style.marginRight = "0.35em";
      a.appendChild(i);
    }
    const text = document.createTextNode(model.get("description") || "Open");
    a.appendChild(text);
  }

  function sync() {
    buildContents();
    a.href = model.get("link") || "#";
    a.target = model.get("target") || "_blank";
    a.title = model.get("tooltip") || "";

    const userClasses = (model.get("class_") || "").trim();
    const defaults = "jupyter-button widget-button link-button";
    el.className = [defaults, userClasses].filter(Boolean).join(" ");

    const style_ = model.get("style_") || "";
    if (style_) a.style.cssText = style_;
    else a.removeAttribute("style");

    if (model.get("disabled")) a.setAttribute("aria-disabled", "true");
    else el.removeAttribute("aria-disabled");
  }

  sync();
  model.on(
    "change:icon change:description change:link change:target change:tooltip change:class_ change:style_ change:disabled",
    sync
  );

  a.addEventListener("click", (ev) => {
    if (model.get("disabled")) {
      ev.preventDefault();
      return;
    }

    const info = {
      ts: Date.now(),
      altKey: !!ev.altKey,
      ctrlKey: !!ev.ctrlKey,
      metaKey: !!ev.metaKey,
      shiftKey: !!ev.shiftKey,
      button: ev.button,
    };

    model.set("last_click", info);
    model.set("clicks", (model.get("clicks") || 0) + 1);
    model.save_changes();

    const prevent = model.get("prevent_default") || !model.get("link");
    if (prevent) {
      ev.preventDefault();
    }
  });

  el.replaceChildren(a);
}
