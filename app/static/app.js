/* 打卡交互：乐观更新 + 局部刷新统计数字，避免整页跳转。 */
(() => {
  "use strict";

  const toastEl = document.getElementById("toast");
  let toastTimer = null;

  function showToast(text) {
    if (!toastEl || !text) return;
    toastEl.textContent = text;
    toastEl.classList.add("show");
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => toastEl.classList.remove("show"), 1600);
  }

  /** 用接口返回的最新数字刷新页面上所有该习惯的统计。 */
  function refreshSummaries(data) {
    const scopes = document.querySelectorAll(`[data-summary-for="${data.habit_id}"]`);
    scopes.forEach((scope) => {
      const fields = { total: data.total, current: data.current, longest: data.longest };
      Object.entries(fields).forEach(([field, value]) => {
        const node = scope.querySelector(`[data-field="${field}"]`);
        if (node) node.textContent = value;
      });
    });
  }

  /** 今日页顶部进度条。 */
  function refreshTodayProgress() {
    const bar = document.querySelector("[data-progress-bar]");
    if (!bar) return;
    const rows = document.querySelectorAll(".habit-row[data-habit-id]");
    const done = document.querySelectorAll(".habit-row.on[data-habit-id]").length;
    const ratio = rows.length ? (done / rows.length) * 100 : 0;
    bar.style.width = `${ratio}%`;
    const text = document.querySelector("[data-progress-text]");
    if (text) text.textContent = `${done} / ${rows.length}`;
  }

  document.addEventListener("click", async (event) => {
    const target = event.target.closest("[data-toggle]");
    if (!target) return;
    event.preventDefault();
    if (target.dataset.busy === "1") return;

    const habitId = Number(target.dataset.habitId);
    const day = target.dataset.day || null;
    const wantOn = !target.classList.contains("on");

    // 先改界面，请求失败再改回来
    target.classList.toggle("on", wantOn);
    target.setAttribute("aria-pressed", wantOn ? "true" : "false");
    target.dataset.busy = "1";

    try {
      const response = await fetch("/api/checkin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ habit_id: habitId, day: day, present: wantOn }),
      });

      if (response.status === 401) {
        window.location.href = "/login";
        return;
      }
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const data = await response.json();
      target.classList.toggle("on", data.present);
      target.setAttribute("aria-pressed", data.present ? "true" : "false");
      refreshSummaries(data);
      refreshTodayProgress();
      showToast(data.present ? "已打卡 ✅" : "已取消");
    } catch (error) {
      target.classList.toggle("on", !wantOn);
      target.setAttribute("aria-pressed", !wantOn ? "true" : "false");
      showToast("网络异常，请重试");
    } finally {
      target.dataset.busy = "";
    }
  });

  // 双击缩放会干扰连续快速点击色块
  document.addEventListener("dblclick", (event) => {
    if (event.target.closest("[data-toggle], .btn, .tab")) event.preventDefault();
  });

  // 覆盖导入不可逆，提交前让用户确认一次
  document.querySelectorAll("form[data-import-form]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      const mode = form.querySelector('input[name="mode"]:checked');
      if (!mode || mode.value !== "replace") return;
      const confirmed = window.confirm(
        "覆盖导入会先清空当前所有习惯和打卡记录（清空前会自动留一份备份文件）。确定继续吗？"
      );
      if (!confirmed) event.preventDefault();
    });
  });
})();
