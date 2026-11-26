"""Station 7, the review page: gate.json -> review.html in the batch folder.

    python -m factory.review <brand> <batch>

One plain file, no server needed. Each piece shows its images or video, the hook and the evidence
behind it, every line of copy beside the facts it rests on, and the gate's result. Approve, reject
and comments are kept in the browser and leave it through the Export button as decisions.json. Opened
through the dashboard (python -m factory.dashboard) they are saved straight into decisions.json instead.
"""
import json
import sys
from html import escape as e

from factory import look, read
from factory.brand import ROOT, BrandError, load_brand
from factory.hooks import AWARENESS, load_evidence

CSS = """
*{box-sizing:border-box}body{margin:0;background:#0d0e10;color:#eceef0;font:16px/1.45 system-ui,sans-serif}
main{max-width:1100px;margin:0 auto;padding:16px}h1{font-size:22px;margin:8px 0}h2{font-size:18px;margin:0}
.note{background:#2a2110;border:1px solid #6b5416;border-radius:10px;padding:10px 14px;margin:12px 0}
.piece{background:#16181b;border:1px solid #2a2d33;border-radius:14px;padding:14px;margin:18px 0}
.head{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.tag{font-size:13px;border-radius:99px;padding:2px 10px;background:#24272c;color:#b4b8c0}
.pass{background:#123524;color:#6fe0a8}.fail{background:#3d1517;color:#ff9a9d}
.media{display:flex;gap:10px;overflow-x:auto;margin:12px 0;align-items:flex-start}
.media a{flex:none;color:#8a8f98;font-size:12px;text-align:center;text-decoration:none}
.media img,.media video{height:340px;display:block;border-radius:8px;border:1px solid #2a2d33;margin-bottom:4px}
table{border-collapse:collapse;width:100%;font-size:14px}td{border-top:1px solid #2a2d33;padding:6px 8px 6px 0;vertical-align:top}
td.w{color:#8a8f98;white-space:nowrap}small,.dim{color:#8a8f98}.scene{color:#f2b84b}td{overflow-wrap:anywhere}
@media(max-width:700px){tr{display:block;border-top:1px solid #2a2d33;padding:6px 0}td{display:block;border:0;padding:1px 0}.media img,.media video{height:300px}}
details{margin:8px 0}summary{cursor:pointer;color:#b4b8c0}ul{margin:6px 0;padding-left:20px}
.act{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}button{font:inherit;border-radius:10px;border:1px solid #3a3e45;background:#22252a;color:#eceef0;padding:10px 18px}
button.on.yes{background:#1d6b45;border-color:#2c9c66}button.on.no{background:#8a2a2e;border-color:#c0474b}
textarea{flex:1 1 260px;min-height:44px;font:inherit;background:#0d0e10;color:#eceef0;border:1px solid #3a3e45;border-radius:10px;padding:8px}
.bar{position:sticky;top:0;background:#0d0e10;padding:10px 0;display:flex;gap:12px;align-items:center;flex-wrap:wrap;border-bottom:1px solid #2a2d33;z-index:2}
"""

JS = """
const KEY = 'review:' + document.body.dataset.key;
let state = JSON.parse(localStorage.getItem(KEY) || '{}');
const [BRAND, BATCH] = document.body.dataset.key.split(':'), timers = {}, where = document.getElementById('where');
let served = false;   // true when the dashboard serves this page: decisions.json in the batch folder is then the record
const keep = () => { if (!served) localStorage.setItem(KEY, JSON.stringify(state)); };
const save = () => { keep(); paint(); };
const dirty = {};     // per piece, what this page changed and has not sent yet: only that is sent, so a comment made on the dashboard is not wiped
const send = (id, field, wait) => { if (!served) return; (dirty[id] = dirty[id] || {})[field] = 1; clearTimeout(timers[id]); timers[id] = setTimeout(() => {
  const s = state[id] || {}, sent = dirty[id], body = {brand: BRAND, batch: BATCH, piece: id};
  delete dirty[id];
  for (const f in sent) body[f] = s[f] || '';
  fetch('/api/decision', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)})
    .then(r => r.json().then(j => {
      if (!r.ok) { where.textContent = 'Not saved to the batch folder. Use Export.'; return; }
      const now = state[id] || {};
      for (const f of ['decision', 'comment']) if (!(f in sent) && !(dirty[id] && f in dirty[id])) now[f] = j[f];   // the rest is what the file holds
      state[id] = now; paint(); where.textContent = 'Saved to decisions.json in the batch folder.'; }))
    .catch(() => { where.textContent = 'Not saved: the dashboard is not answering. Use Export.'; }); }, wait); };
function paint() {
  let yes = 0, no = 0;
  document.querySelectorAll('.piece').forEach(p => {
    const s = state[p.id] || {};
    p.querySelector('.yes').classList.toggle('on', s.decision === 'approve');
    p.querySelector('.no').classList.toggle('on', s.decision === 'reject');
    if (p.querySelector('textarea').value !== (s.comment || '')) p.querySelector('textarea').value = s.comment || '';
    yes += s.decision === 'approve'; no += s.decision === 'reject';
  });
  document.getElementById('count').textContent = yes + ' approved, ' + no + ' rejected';
}
document.querySelectorAll('.piece').forEach(p => {
  const set = d => { const s = state[p.id] || {}; s.decision = s.decision === d ? '' : d; s.at = new Date().toISOString(); state[p.id] = s; save(); send(p.id, 'decision', 0); };
  p.querySelector('.yes').onclick = () => set('approve');
  p.querySelector('.no').onclick = () => set('reject');
  p.querySelector('textarea').oninput = ev => { const s = state[p.id] || {}; s.comment = ev.target.value; s.at = new Date().toISOString(); state[p.id] = s; keep(); send(p.id, 'comment', 800); };
});
document.getElementById('export').onclick = () => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify({batch: document.body.dataset.key, decisions: state}, null, 1)], {type: 'application/json'}));
  a.download = 'decisions.json'; a.click();
};
paint();
if (location.protocol.startsWith('http')) fetch('/api/job').then(r => { if (!r.ok) throw 0; served = true; return fetch('decisions.json'); })
  .then(r => r.ok ? r.json() : {}).then(j => { state = j.decisions || {}; where.textContent = 'Decisions save to decisions.json in the batch folder.'; paint(); })
  .catch(() => {});   // a plain file or another server: the browser keeps them, as before
"""


def build(slug, batch):
    brand = load_brand(slug)
    folder = ROOT / "runs" / slug / batch
    if not (folder / "gate.json").is_file():
        raise BrandError(f"{folder / 'gate.json'} is missing: run a production lane first (python -m factory.statics {slug} {batch})")
    gate = json.loads((folder / "gate.json").read_text(encoding="utf-8"))
    hooks = {h["id"]: h for h in json.loads((folder / "hooks.json").read_text(encoding="utf-8"))["hooks"]}
    evidence = load_evidence(folder / "evidence.md")
    facts = brand["facts"]
    unconfirmed = sum(f["status"] != "confirmed by Nate" for f in facts.values())
    passed = sum(not p["problems"] for p in gate["pieces"].values())
    used = set()
    reads = read.saved(folder)
    seen_lines = {}                                     # one entry per distinct line: (piece, where, text, ids, verdict)
    for pid, p in gate["pieces"].items():
        for where, text, ids in p["lines"]:
            if where not in read.SKIP:
                seen_lines.setdefault(read.key(text, ids, facts), (pid, where, text, ids, read.verdict(folder, text, ids, facts, reads)))
    bare = [x for x in seen_lines.values() if not x[3]]
    flagged = [x for x in seen_lines.values() if x[4] and not x[4]["ok"]]
    unread = sum(x[4] is None for x in seen_lines.values())

    out = [f"<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
           f"<title>Review: {e(brand['brand']['name'])}, {e(batch)}</title><style>{CSS}</style>"
           f"<body data-key='{e(slug)}:{e(batch)}'><main><h1>{e(brand['brand']['name'])}: {e(batch)}</h1>"
           f"<div class=dim>{len(gate['pieces'])} pieces, {passed} pass the automatic checks. Checked {e(gate['checked'])}.</div>"]
    if unconfirmed:
        out.append(f"<div class=note><b>Drafts.</b> {unconfirmed} of {len(facts)} facts in facts.md still say \"needs Nate\". "
                   f"Nothing here can run until he confirms them. Nothing has been posted or sent anywhere.</div>")
    row = lambda x: (f"<tr><td class=w>{e(x[0])}<br>{e(x[1])}</td><td>{e(x[2])}</td><td><small>"
                     + (f"<span class=fail style='background:none'>NOT BACKED: {e(x[4]['why'])}</span>" if x[4] and not x[4]['ok'] else
                        f"read: ok ({e(x[4]['why'])})" if x[4] else "<span class=scene>nobody has read it</span>") + "</small></td></tr>")
    out.append(f"<div class=note><b>Claims to read.</b> {len(seen_lines)} lines of copy. "
               f"A fresh reader flagged <b>{len(flagged)}</b> as saying more than their facts; <b>{unread}</b> nobody has read yet "
               f"(<code>python -m factory.read {e(slug)} {e(batch)}</code>). {len(bare)} cite no fact at all."
               + (f"<h3 style='margin:10px 0 4px'>Flagged by the reader</h3><table>{''.join(map(row, flagged))}</table>" if flagged else "")
               + (f"<details><summary>The {len(bare)} lines that cite no fact</summary><table>{''.join(map(row, bare))}</table></details>" if bare else "")
               + "</div>")
    out.append("<div class=bar><span id=count></span><button id=export>Export decisions</button>"
               "<small id=where>Decisions stay in this browser until you export them.</small></div>")

    for pid, p in gate["pieces"].items():
        hook = hooks.get(pid.split("-")[0], {})
        ok = not p["problems"]
        out.append(f"<section class=piece id='{e(pid)}'><div class=head><h2>{e(pid)}</h2>"
                   f"<span class='tag {'pass' if ok else 'fail'}'>{'passes the gate' if ok else 'FAILED the gate'}</span>"
                   f"<span class=tag>{e(p['kind'])}</span><span class=tag>{e(hook.get('customer', '?'))}</span>"
                   f"<span class=tag>{e(hook.get('type', '?'))} hook, {e(AWARENESS.get(hook.get('type'), '?'))}</span></div>")
        if hook:
            out.append(f"<div style='margin-top:8px'>Hook: \"{e(hook['spoken'])}\"</div>")
        if p.get("seconds") or p.get("notes"):
            out.append("<div class=dim style='margin-top:6px'>" + " ".join(
                ([f"{p['seconds']:.1f} seconds."] if p.get("seconds") else []) + [e(n) for n in p.get("notes", [])]) + "</div>")
        mp4s = {n: folder / rel for n, rel in p["files"].items() if rel.endswith(".mp4") and (folder / rel).is_file()}
        if mp4s:
            seen = look.note(folder, pid, mp4s)
            out.append(f"<div class=dim style='margin-top:6px'><b>Look, {e(seen['at'])}:</b> {e(seen['note'])}</div>" if seen else
                       "<div class=fail style='margin-top:6px;background:none'>Look: nobody has looked at this video since it was last rendered.</div>")
        if not ok:
            out.append("<ul>" + "".join(f"<li class=fail style='background:none'>{e(x)}</li>" for x in p["problems"]) + "</ul>")
        out.append("<div class=media>")
        for name, rel in p["files"].items():
            tag = f"<video src='{e(rel)}' controls preload=metadata></video>" if rel.endswith(".mp4") else f"<img src='{e(rel)}' loading=lazy alt='{e(pid)} {e(name)}'>"
            out.append(f"<a href='{e(rel)}' target=_blank>{tag}{e(name)}</a>")
        out.append("</div><table>")
        for where, text, ids in p["lines"]:
            used.update(ids)
            src = ", ".join(f"<b>{e(i)}</b> {e(facts[i]['text'])}" if i in facts else f"<b class=fail>{e(i)} (not in facts.md)</b>" for i in ids)
            if not ids:
                src = "<span class=dim>brand.json</span>" if where in ("label", "url") else "<span class=scene>cites no fact</span>"
            if where not in read.SKIP:
                v = read.verdict(folder, text, ids, facts, reads)
                src += ("<br><span class=fail style='background:none'>Reader: NOT BACKED. " + e(v["why"]) + "</span>" if v and not v["ok"] else
                        "<br><span class=dim>Reader: ok</span>" if v else "<br><span class=dim>Reader: not read</span>")
            out.append(f"<tr><td class=w>{e(where)}</td><td>{e(text)}</td><td><small>{src}</small></td></tr>")
        out.append("</table>")
        if hook.get("evidence"):
            out.append("<details><summary>Why this hook (evidence, none of it this brand's own results)</summary><ul>" + "".join(
                f"<li><b>{e(i)}</b> [{e(evidence[i]['grade'])}] {e(evidence[i]['text'])} <small>{e(evidence[i]['source'])}</small></li>"
                for i in hook["evidence"] if i in evidence) + "</ul></details>")
        out.append("<div class=act><button class=yes>Approve</button><button class=no>Reject</button>"
                   "<textarea placeholder='Comment (what to change)'></textarea></div></section>")

    out.append("<h2 style='margin-top:28px'>Facts these pieces use</h2><table>" + "".join(
        f"<tr><td class=w><b>{e(i)}</b></td><td>{e(facts[i]['text'])}</td><td><small>{e(facts[i]['status'])}<br>{e(facts[i]['source'])}</small></td></tr>"
        for i in sorted(used) if i in facts) + f"</table></main><script>{JS}</script></body></html>")
    page = folder / "review.html"
    page.write_text("\n".join(out), encoding="utf-8")
    return page, len(gate["pieces"]), passed


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: python -m factory.review <brand> <batch>")
    try:
        page, total, passed = build(sys.argv[1], sys.argv[2])
        print(f"{page} ({total} pieces, {passed} pass)")
    except BrandError as err:
        sys.exit(f"error: {err}")
