const $ = (id) => document.getElementById(id);
const api = async (url, opts) => {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (e) {}
    throw new Error(detail);
  }
  return res.json();
};

const SCREENS = ["setup", "turn", "pass", "reveal", "winner"];

function show(name) {
  SCREENS.forEach((s) => $("screen-" + s).classList.toggle("hidden", s !== name));
}

function setLoading(on) {
  $("loading").classList.toggle("hidden", !on);
}

// ---------------- SETUP ----------------
function initSetup() {
  let count = 3;
  const namesBox = $("names");
  const render = () => {
    namesBox.innerHTML = "";
    for (let i = 0; i < count; i++) {
      const input = document.createElement("input");
      input.className = "name-input";
      input.placeholder = "Joueur " + (i + 1);
      input.dataset.idx = i;
      namesBox.appendChild(input);
    }
    $("playerCount").textContent = count;
    $("setupError").textContent = "";
  };
  $("minus").onclick = () => { count = Math.max(2, count - 1); render(); };
  $("plus").onclick = () => { count = Math.min(12, count + 1); render(); };
  $("startBtn").onclick = async () => {
    const inputs = namesBox.querySelectorAll(".name-input");
    const players = Array.from(inputs).map((i) => i.value.trim());
    if (players.some((p) => !p)) {
      $("setupError").textContent = "Renseigne tous les noms.";
      return;
    }
    try {
      setLoading(true);
      const created = await api("/api/games", {
        method: "POST",
        body: JSON.stringify({ players }),
      });
      localStorage.setItem("footquiz_game", created.game_id);
      await refresh();
    } catch (e) {
      $("setupError").textContent = e.message;
    } finally {
      setLoading(false);
    }
  };
  render();
}

// ---------------- WELCOME / state dispatch ----------------
async function refresh() {
  setLoading(true);
  try {
    const id = localStorage.getItem("footquiz_game");
    if (!id) {
      show("setup");
      return;
    }
    const st = await api("/api/games/" + id);
    if (st.status === "finished") {
      $("winnerName").textContent = st.winner;
      show("winner");
    } else if (st.next_user_index !== null) {
      await loadTurn(st);
    } else if (st.round_complete) {
      await loadReveal();
    } else {
      alert("État inconnu, recharge la page.");
    }
  } catch (e) {
    alert(e.message);
  } finally {
    setLoading(false);
  }
}

// ---------------- TURN ----------------
async function loadTurn(st) {
  const id = localStorage.getItem("footquiz_game");
  const t = await api(`/api/games/${id}/turn`);

  $("turnUserName").textContent = t.user_name;
  $("playerName").textContent = t.footballer.name;
  $("playerPhoto").src = t.footballer.portrait_url || "";
  $("turnError").textContent = "";

  const qBox = $("questions");
  qBox.innerHTML = "";
  const selection = {};

  t.questions.forEach((q, qi) => {
    const card = document.createElement("div");
    card.className = "question";
    const title = document.createElement("h3");
    const qnum = qi + 1;
    title.textContent = qnum + ". " + q.question;
    card.appendChild(title);

    const choices = document.createElement("div");
    choices.className = "choices";
    q.choices.forEach((c, ci) => {
      const btn = document.createElement("button");
      btn.className = "choice";
      btn.textContent = c;
      btn.onclick = () => {
        choices.querySelectorAll(".choice").forEach((b) => b.classList.remove("selected"));
        btn.classList.add("selected");
        selection[qi] = ci;
        checkReady(t.questions, selection);
      };
      choices.appendChild(btn);
    });
    card.appendChild(choices);
    qBox.appendChild(card);
  });

  $("submitBtn").classList.remove("hidden");
  $("submitBtn").disabled = true;

  $("submitBtn").onclick = async () => {
    const answers = t.questions.map((_, i) => selection[i]);
    try {
      setLoading(true);
      const res = await api(`/api/games/${id}/answers`, {
        method: "POST",
        body: JSON.stringify({ user_index: t.user_index, answers }),
      });
      if (res.next_user_index === null) {
        await refresh();
      } else {
        const nextName = st.players.find((p) => p.index === res.next_user_index);
        showPass(nextName ? nextName.name : "joueur suivant");
      }
    } catch (e) {
      $("turnError").textContent = e.message;
    } finally {
      setLoading(false);
    }
  };
  show("turn");
}

function checkReady(questions, selection) {
  const ready = questions.every((_, i) => selection[i] !== undefined);
  $("submitBtn").disabled = !ready;
}

// ---------------- PASS PHONE ----------------
function showPass(name) {
  $("passName").textContent = name;
  $("passBtn").onclick = refresh;
  show("pass");
}

// ---------------- REVEAL ----------------
let revealData = null;
let revealIndex = 0;

async function loadReveal() {
  const id = localStorage.getItem("footquiz_game");
  revealData = await api(`/api/games/${id}/reveal`);
  revealIndex = 0;

  $("revealTitle").textContent = "Manche " + revealData.round_number + " — réponses";
  $("revealPlayerName").textContent = revealData.footballer.name;
  $("revealPhoto").src = revealData.footballer.portrait_url || "";
  $("revealNextBtn").textContent = "Suivant";
  drawReveal();
  show("reveal");
}

function drawReveal() {
  const body = $("revealBody");
  body.innerHTML = "";
  const qs = revealData.questions;

  if (revealIndex < qs.length) {
    const q = qs[revealIndex];
    const card = document.createElement("div");
    card.className = "card";

    const title = document.createElement("h3");
    title.textContent = (revealIndex + 1) + ". " + q.question;
    card.appendChild(title);

    const choices = document.createElement("div");
    choices.className = "choices";
    q.choices.forEach((c, ci) => {
      const div = document.createElement("button");
      div.className = "choice";
      div.textContent = c;
      if (ci === q.correct_index) div.classList.add("reveal-correct");
      const badGuess = revealData.results.some(
        (r) => r.answers[revealIndex] && r.answers[revealIndex].chosen_index === ci && !r.answers[revealIndex].is_correct
      );
      if (badGuess && ci !== q.correct_index) div.classList.add("reveal-wrong");
      div.disabled = true;
      choices.appendChild(div);
    });
    card.appendChild(choices);

    const strip = document.createElement("div");
    strip.className = "answer-strip";
    revealData.results.forEach((r) => {
      const a = r.answers[revealIndex];
      const row = document.createElement("div");
      row.className = "user-answer " + (a && a.is_correct ? "ok" : "bad");
      const label = document.createElement("span");
      label.textContent = r.name;
      const mark = document.createElement("span");
      mark.className = "mark";
      if (!a) mark.textContent = "—";
      else if (a.is_correct) mark.textContent = "✓";
      else mark.textContent = "✗ " + q.choices[a.chosen_index];
      row.appendChild(label);
      row.appendChild(mark);
      strip.appendChild(row);
    });
    card.appendChild(strip);
    body.appendChild(card);

    $("revealNextBtn").textContent =
      revealIndex === qs.length - 1 ? "Voir les scores" : "Suivant";
  } else {
    // Standings
    const card = document.createElement("div");
    card.className = "card";
    const h = document.createElement("h1");
    h.textContent = "Scores";
    card.appendChild(h);

    const standings = document.createElement("div");
    standings.className = "standings";
    const active = revealData.results.filter((r) => !r.eliminated);
    const sorted = [...active].sort((a, b) => b.score - a.score);
    const minScore = Math.min(...active.map((r) => r.score));
    const losers = active.filter((r) => r.score === minScore);

    sorted.forEach((r, i) => {
      const row = document.createElement("div");
      row.className = "stand-row";
      if (i === 0) row.classList.add("first");
      if (losers.some((l) => l.index === r.index) && losers.length < active.length)
        row.classList.add("loser");
      const name = document.createElement("span");
      name.textContent = (i + 1) + ". " + r.name;
      const score = document.createElement("span");
      score.className = "score";
      score.textContent = r.score + "/" + revealData.questions.length;
      row.appendChild(name);
      row.appendChild(score);
      standings.appendChild(row);
    });
    card.appendChild(standings);

    const note = document.createElement("p");
    if (losers.length === revealData.results.length) {
      note.textContent = "Égalité parfaite — personne n'est éliminé !";
    } else {
      note.textContent = "Éliminé" + (losers.length > 1 ? "s : " : " : ") + losers.map((l) => l.name).join(", ");
    }
    note.style.cssText = "color:#ffc93c;text-align:center;margin-top:12px;font-weight:600;";
    card.appendChild(note);
    body.appendChild(card);

    $("revealNextBtn").textContent = "Manche suivante";
  }
}

$("revealNextBtn").onclick = async () => {
  const qs = revealData.questions;
  if (revealIndex < qs.length) {
    revealIndex++;
    if (revealIndex === qs.length) {
      $("revealNextBtn").textContent = "Manche suivante";
    }
    drawReveal();
  } else {
    const id = localStorage.getItem("footquiz_game");
    setLoading(true);
    try {
      const st = await api(`/api/games/${id}/next-round`, { method: "POST" });
      if (st.status === "finished") {
        $("winnerName").textContent = st.winner;
        show("winner");
      } else {
        await refresh();
      }
    } finally {
      setLoading(false);
    }
  }
};

// ---------------- WINNER ----------------
$("newGameBtn").onclick = () => {
  localStorage.removeItem("footquiz_game");
  show("setup");
};

// ---------------- START ----------------
initSetup();
if (localStorage.getItem("footquiz_game")) refresh();