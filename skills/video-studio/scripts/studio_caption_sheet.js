// Read a video's burned-in captions inside YouTube Studio (or any page with a <video>) when the project files aren't at hand.
// Paste into the page (browser javascript tool) with the upload/edit dialog open, then:
//   capSheet(0)            -> starts in the background (returns at once); poll window.capDone until it's set
//   capPage(0), capPage(1) -> scroll the sheet; screenshot/zoom each page and read the captions in order
//   document.getElementById('capsheet').style.display = 'none'   // hide it before typing into the dialog
// It seeks the visible <video> every `step` s and stacks the caption band (fraction y0..y1 of the frame) from each moment
// on a fixed canvas, 4 columns, each strip labelled with its time. Defaults fit 9:16 Shorts with captions at ~70 % height.
// Gotchas: right after the dialog opens, the preview may report a PARTIAL duration (a 38 s Short read as 24 s), so wait
// ~6 s first and check `capDone`'s duration against the player; the run can outlast a 45 s tool timeout, which is why it's async.
window.capSheet = async function (start = 0, step = 0.7, y0 = 0.66, y1 = 0.79) {
  const v = [...document.querySelectorAll('video')].filter(v => v.duration > 1 && v.offsetParent).pop();
  if (!v) { window.capDone = 'no visible video'; return; }
  v.muted = true; v.pause();
  await new Promise(r => { if (v.readyState >= 1) r(); else v.addEventListener('loadedmetadata', r, { once: true }); });
  const W = v.videoWidth, H = v.videoHeight, bh = Math.round((y1 - y0) * H);
  const n = Math.floor((v.duration - start) / step) + 1, cols = 4, rows = Math.ceil(n / cols), lab = 16;
  const sw = W, sh = bh;
  let c = document.getElementById('capsheet');
  if (!c) { c = document.createElement('canvas'); c.id = 'capsheet'; document.body.appendChild(c); }
  c.width = cols * (sw + 6); c.height = rows * (sh + lab);
  Object.assign(c.style, { display: 'block', position: 'fixed', left: '0', top: '0', zIndex: 999999,
                           width: c.width + 'px', height: c.height + 'px', background: '#000' });
  const g = c.getContext('2d'); g.fillStyle = '#000'; g.fillRect(0, 0, c.width, c.height); g.font = '13px sans-serif';
  for (let i = 0; i < n; i++) {
    const t = Math.min(start + i * step, v.duration - 0.05);
    await Promise.race([new Promise(r => { v.addEventListener('seeked', r, { once: true }); v.currentTime = t; }),
                        new Promise(r => setTimeout(r, 2500))]);
    const x = (i % cols) * (sw + 6), y = Math.floor(i / cols) * (sh + lab);
    g.fillStyle = '#ff0'; g.fillText(t.toFixed(1), x + 2, y + 12);
    g.drawImage(v, 0, y0 * H, W, bh, x, y + lab, sw, sh);
  }
  window.capPage = p => { c.style.top = (-p * 770) + 'px'; return Math.ceil(c.height / 770); };
  window.capDone = `dur ${v.duration.toFixed(1)} s, ${n} strips, pages ${Math.ceil(c.height / 770)}`;
};
window.capDone = null;
'capSheet ready';
