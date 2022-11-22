const buttonId = "dk-analyze-btn"
const iframeId = "dk-analyze-iframe"


function init() {
  const url = window.location.href

  const i = url.indexOf("fight=")
  if (i < 0) {
    console.log("no fight")
    hideButton()
    removeIframe()
    return
  }

  if (url.indexOf("source=") < 0) {
    console.log("no source")
    hideButton()
    removeIframe()
    return
  }

  addAnalyzeButton()
}

function hideButton() {
  const button = document.getElementById(buttonId)

  if (button) {
    console.log("hiding")
    button.style.setProperty("display", "none", "important")
  }
}

function removeIframe() {
  const iframe = document.getElementById(iframeId)

  if (iframe) {
    iframe.remove()
  }
}

function hideReport() {
  document.getElementById("report-view-contents").style.display = "none"
}

function showReport() {
  document.getElementById("report-view-contents").style.display = "block"
}

function addLocationObserver(callback) {
  const config = { attributes: false, childList: true, subtree: true }
  const observer = new MutationObserver(callback)
  observer.observe(document.body, config)
}

function handler() {
  if (document.getElementById(iframeId)) {
    return
  }

  const url = window.location.href
  const fight = url.match(/fight=(\d+)/)[1]
  const source = url.match(/source=(\d+)/)[1]
  console.log(fight, source)
  const tabs = document.getElementById("top-level-view-tabs")
  for (let link of tabs.children) {
    link.classList.remove("selected")
  }
  document.getElementById(buttonId).classList.add("selected")
  document.body.classList.remove("compare")
  hideReport()

  const iframe = document.createElement("iframe")
  iframe.setAttribute("id", iframeId)
  iframe.src = "http://localhost:5173/"
  iframe.style = "min-width:100%;border:none;overflow:hidden;"
  const report = document.getElementById("report-view-contents")
  report.parentNode.insertBefore(iframe, report)
  iFrameResize({ log: true, scrolling: true }, `#${iframeId}`)
}

function addAnalyzeButton() {
  let button = document.getElementById(buttonId)

  if (button) {
    console.log("showing")
    button.style.display = "block"
    return
  }

  button = document.createElement("a")
  button.setAttribute("id", buttonId)
  button.className = "big-tab view-type-tab"

  const icon = document.createElement("span")
  icon.className = "zmdi zmdi-eye"
  icon.style.color = "darkred"

  const text = document.createElement("span")
  text.innerHTML = "<br> DK Analyze"
  text.className = "big-tab-text"
  text.style.color = "darkred"

  const tabs = document.getElementById("top-level-view-tabs")
  button.appendChild(icon)
  button.appendChild(text)
  button.onclick = handler
  tabs.onclick = (e) => {
    const btn = document.getElementById(buttonId)
    const target = e.target

    if (!target.isEqualNode(btn) && !target.parentNode.isEqualNode(btn)) {
      btn.classList.remove("selected")
      target.classList.add("selected")
      target.parentNode.classList.add("selected")
      removeIframe()
      showReport()
    }
  }
  tabs.insertBefore(button, tabs.firstChild)
}

addLocationObserver(init)
init()

