const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

function normalizeCode(text){
  const t = (text||"").replace(/[,;]/g,".").replace(/O/g,"0").replace(/I/g,"1");
  const known = ["1.8.0","1.8.1","1.8.2","0.9.1","0.9.2","2.8.0","0.2.2","E.E.0"];
  for (const c of known){ if(t.includes(c) || t.replace(/\s/g,"").includes(c)) return c; }
  const m = t.match(/[012E]\.?[892E]\.?[012E]/);
  return m ? m[0].replace(/^(\d)(\d)(\d)$/,"$1.$2.$3") : "";
}
function bestNumber(text){
  const cleaned = (text||"").replace(/[Oo]/g,"0").replace(/[Il|]/g,"1");
  const nums = cleaned.match(/\d{3,}/g) || [];
  if(!nums.length) return "";
  return nums.sort((a,b)=>b.length-a.length)[0];
}
function setReading(code, value){
  const input = document.querySelector(`[data-code="${code}"]`);
  if(input && value && !input.value) input.value = value;
}

async function runOCR(imageUrl, container){
  const log = container.querySelector('.ocr');
  log.textContent = 'OCR σε εξέλιξη...';
  try{
    const { data } = await Tesseract.recognize(imageUrl, 'eng', {
      logger: m => { if(m.status) log.textContent = `${m.status} ${Math.round((m.progress||0)*100)}%`; }
    });
    const text = data.text || '';
    log.textContent = text.trim() || 'Δεν διαβάστηκε καθαρό κείμενο. Συμπλήρωσε χειροκίνητα.';
    const code = normalizeCode(text);
    const num = bestNumber(text);
    if(code && num) setReading(code, num);
  }catch(e){
    log.textContent = 'OCR απέτυχε. Συμπλήρωσε χειροκίνητα.';
  }
}

$('#uploadBtn').addEventListener('click', async () => {
  const files = $('#photos').files;
  if(!files.length) return alert('Επίλεξε πρώτα φωτογραφίες.');
  const fd = new FormData();
  for(const f of files) fd.append('photos', f);
  $('#uploadBtn').disabled = true;
  $('#uploadBtn').textContent = 'Ανεβάζω...';
  const res = await fetch('/upload', {method:'POST', body:fd});
  const data = await res.json();
  $('#uploadBtn').disabled = false;
  $('#uploadBtn').textContent = 'Ανέβασμα & OCR';
  for(const file of data.files){
    const card = document.createElement('div');
    card.className='shot';
    card.innerHTML = `<img src="${file.processed}" alt="meter"><div><strong>${file.filename}</strong><p class="ocr">Αναμονή...</p></div>`;
    $('#gallery').prepend(card);
    runOCR(file.processed, card);
  }
});

$('#calcBtn').addEventListener('click', async () => {
  const readings = {};
  $$('[data-code]').forEach(i => readings[i.dataset.code] = i.value);
  const res = await fetch('/calculate', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({supply_type:$('#supplyType').value, readings})});
  const data = await res.json();
  let html = `<h3>Αποτέλεσμα καταχώρισης</h3><p><strong>Τύπος:</strong> ${data.supply_type}</p>`;
  for(const [k,v] of Object.entries(data.fields)) html += `<span class="pill"><strong>${k}:</strong> ${v || '—'}</span>`;
  if($('#meterNo').value) html += `<p><strong>Αριθμός:</strong> ${$('#meterNo').value}</p>`;
  if(data.warnings.length) html += `<p class="warn">${data.warnings.join('<br>')}</p>`; else html += `<p class="ok">Έτοιμο για καταχώριση. Έλεγξε οπτικά τις φωτογραφίες πριν την υποβολή.</p>`;
  $('#result').innerHTML = html;
  $('#result').classList.remove('hidden');
});
