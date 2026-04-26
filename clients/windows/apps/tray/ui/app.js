const statusEl = document.getElementById('status');
document.getElementById('initialize').addEventListener('click', () => {
  const payload = {
    panelUrl: document.getElementById('panelUrl').value,
    pairCode: document.getElementById('pairCode').value,
    nodeName: document.getElementById('nodeName').value,
    listenPort: Number(document.getElementById('listenPort').value),
    exposeControlBridge: document.getElementById('exposeControlBridge').checked,
  };
  statusEl.textContent = JSON.stringify(payload, null, 2);
});
