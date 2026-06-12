const suggestionsEl = document.getElementById("suggestions");
const historyListEl = document.getElementById("history-list");
const historyEmptyEl = document.getElementById("history-empty");
const historyCountEl = document.getElementById("history-count");
const queryForm = document.getElementById("query-form");
const questionInput = document.getElementById("question-input");
const submitBtn = document.getElementById("submit-btn");
const btnLabel = submitBtn.querySelector(".btn-label");
const btnSpinner = submitBtn.querySelector(".btn-spinner");

let history = [];
let nextId = 1;
let isSubmitting = false;

const CHEVRON_SVG = `<svg class="accordion-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M9 18l6-6-6-6"/></svg>`;

function apiUrl(path) {
  const base = (window.APP_CONFIG?.API_BASE_URL ?? "").replace(/\/$/, "");
  return `${base}${path}`;
}

async function loadSuggestions() {
  try {
    const res = await fetch(apiUrl("/api/suggestions"));
    const data = await res.json();
    renderSuggestions(data.suggestions);
  } catch {
    renderSuggestions([
      "Give me the names of 10 players",
      "Who are the top 5 most valuable players?",
      "Which country has produced the most players?",
    ]);
  }
}

function renderSuggestions(items) {
  suggestionsEl.innerHTML = items
    .map(
      (text) =>
        `<button type="button" class="suggestion-chip" data-question="${escapeAttr(text)}">${escapeHtml(text)}</button>`
    )
    .join("");

  suggestionsEl.querySelectorAll(".suggestion-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      questionInput.value = chip.dataset.question;
      questionInput.focus();
      submitQuestion(chip.dataset.question);
    });
  });
}

function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escapeAttr(str) {
  return escapeHtml(str).replace(/'/g, "&#39;");
}

function updateHistoryCount() {
  const count = history.length;
  historyCountEl.textContent = `${count} question${count === 1 ? "" : "s"}`;
  historyEmptyEl.classList.toggle("hidden", count > 0);
}

function toggleItem(id) {
  const item = history.find((entry) => entry.id === id);
  if (!item) return;
  item.expanded = !item.expanded;
  renderHistory();
}

function renderHistory() {
  historyListEl.innerHTML = history
    .map((entry) => {
      const isOpen = entry.expanded;
      const statusClass = entry.status;
      const statusLabel =
        entry.status === "loading"
          ? "Running"
          : entry.status === "error"
            ? "Error"
            : "Done";

      let panelContent = "";
      if (entry.status === "loading") {
        panelContent = `
          <div class="loading-block">
            <span class="spinner" aria-hidden="true"></span>
            <span>Generating SQL and fetching results…</span>
          </div>`;
      } else if (entry.status === "error") {
        panelContent = `<p class="error-text">${escapeHtml(entry.error)}</p>`;
      } else {
        const tableHtml = buildTable(entry.result);
        panelContent = `
          <div class="answer-block">
            <p class="answer-label">Answer</p>
            <p class="answer-text">${escapeHtml(entry.result.answer)}</p>
          </div>
          <div class="sql-block">
            <p class="sql-label">SQL Query</p>
            <pre class="sql-code">${escapeHtml(entry.result.sql_query)}</pre>
          </div>
          ${tableHtml}`;
      }

      return `
        <article class="accordion-item ${isOpen ? "is-open" : ""} is-${entry.status}" role="listitem">
          <button
            type="button"
            class="accordion-trigger"
            aria-expanded="${isOpen}"
            data-id="${entry.id}"
          >
            ${CHEVRON_SVG}
            <span class="accordion-question">${escapeHtml(entry.question)}</span>
            <span class="accordion-status ${statusClass}">${statusLabel}</span>
          </button>
          <div class="accordion-panel">
            <div class="accordion-panel-inner">
              <div class="accordion-content">${panelContent}</div>
            </div>
          </div>
        </article>`;
    })
    .join("");

  historyListEl.querySelectorAll(".accordion-trigger").forEach((trigger) => {
    trigger.addEventListener("click", () => {
      toggleItem(Number(trigger.dataset.id));
    });
  });

  updateHistoryCount();
}

function buildTable(result) {
  if (!result.rows || result.rows.length === 0) {
    return "";
  }

  const headers = result.columns
    .map((col) => `<th>${escapeHtml(String(col))}</th>`)
    .join("");

  const body = result.rows
    .map((row) => {
      const cells = result.columns
        .map((col) => `<td>${escapeHtml(formatCell(row[col]))}</td>`)
        .join("");
      return `<tr>${cells}</tr>`;
    })
    .join("");

  const notes = [];
  if (result.rows_truncated) {
    notes.push(`Showing the first ${result.rows.length} rows (results truncated).`);
  }
  if (result.columns_truncated) {
    notes.push("Some columns were omitted to keep the response manageable.");
  }
  const note = notes.length
    ? `<p class="table-note">${notes.join(" ")}</p>`
    : "";

  return `
    <div class="table-block">
      <p class="table-label">Query Results</p>
      <table class="data-table">
        <thead><tr>${headers}</tr></thead>
        <tbody>${body}</tbody>
      </table>
      ${note}
    </div>`;
}

function formatCell(value) {
  if (value === null || value === undefined) return "—";
  return String(value);
}

function setSubmitting(active) {
  isSubmitting = active;
  submitBtn.disabled = active;
  btnLabel.hidden = active;
  btnSpinner.hidden = !active;
}

async function submitQuestion(question) {
  const trimmed = question.trim();
  if (!trimmed || isSubmitting) return;

  const entry = {
    id: nextId++,
    question: trimmed,
    status: "loading",
    expanded: true,
    result: null,
    error: null,
  };

  history.unshift(entry);
  questionInput.value = "";
  renderHistory();
  setSubmitting(true);

  try {
    const res = await fetch(apiUrl("/api/query"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: trimmed }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Something went wrong.");
    }

    entry.status = "done";
    entry.result = data;
  } catch (err) {
    entry.status = "error";
    entry.error = err.message || "Failed to run query.";
  } finally {
    renderHistory();
    setSubmitting(false);
  }
}

queryForm.addEventListener("submit", (event) => {
  event.preventDefault();
  submitQuestion(questionInput.value);
});

questionInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    submitQuestion(questionInput.value);
  }
});

loadSuggestions();
