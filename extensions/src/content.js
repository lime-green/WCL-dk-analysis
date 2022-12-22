const buttonId = "dk-analyze-btn"
const iframeId = "dk-analyze-iframe"
let currentParams = null

function isEqual(obj1, obj2) {
    var props1 = Object.getOwnPropertyNames(obj1);
    var props2 = Object.getOwnPropertyNames(obj2);

    if (props1.length !== props2.length) {
        return false;
    }
    for (let i = 0; i < props1.length; i++) {
        let val1 = obj1[props1[i]];
        let val2 = obj2[props1[i]];
        let isObjects = isObject(val1) && isObject(val2);
        if (isObjects && !isEqual(val1, val2) || !isObjects && val1 !== val2) {
            return false;
        }
    }
    return true;
}

function isObject(object) {
  return object != null && typeof object === 'object';
}

function init() {
  const url = window.location.href

  if (url.indexOf("fight=") < 0) {
    hideButton()
    removeIframe()
    return
  }

  if (url.indexOf("source=") < 0) {
    hideButton()
    removeIframe()
    return
  }

  if (url.indexOf("/reports/") < 0) {
    hideButton()
    removeIframe()
  }

  addAnalyzeButton()

  const params = parseParams()
  if (currentParams && !isEqual(currentParams, params)) {
    document.getElementById(iframeId).src = getFrameURL(params)
    currentParams = params
  }
}

function hideButton() {
  const button = document.getElementById(buttonId)

  if (button) {
    button.style.setProperty("display", "none", "important")
  }
}

function removeIframe() {
  const iframe = document.getElementById(iframeId)

  if (iframe) {
    iframe.remove()
  }

  currentParams = null
}

function parseParams() {
  const url = window.location.href
  let fight = url.match(/fight=(\w+)/)[1]
  fight = fight === "last" ? -1 : fight
  const source = url.match(/source=(\d+)/)[1]
  const report = url.match(/reports\/([:\w]+)[\/#]/)[1]

  return {fight, source, report}
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

function debounce(func, timeout = 300){
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => { func.apply(this, args); }, timeout);
  };
}

function handler() {
  if (document.getElementById(iframeId)) {
    return
  }

  document.body.classList.remove("compare")
  hideReport()

  const iframe = document.createElement("iframe")
  const params = parseParams()
  iframe.src = getFrameURL(params)
  iframe.setAttribute("id", iframeId)
  iframe.style = "min-width:100%;border:none;overflow:hidden;"
  iframe.scrolling = "no"
  const report_node = document.getElementById("report-view-contents")
  report_node.parentNode.insertBefore(iframe, report_node)
  currentParams = params

  // debounce to prevent flickering
  window.addEventListener("message", debounce(e => {
    if (e.data > 0) {
      document.getElementById(iframeId).height = e.data + 'px';
    }
  }, 10))
}

function getFrameURL(params) {
  if (window.chrome && window.chrome.runtime.id === "aalplhgcljbeccbfkbdfhkfnenfmjhdf") {
    return `http://localhost:5173?${new URLSearchParams(params)}`
  }
  return `https://d2krnvrnlw0zwg.cloudfront.net/?${new URLSearchParams(params)}`
}

function addAnalyzeButton() {
  let button = document.getElementById(buttonId)

  if (button) {
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
      removeIframe()
      showReport()
    }
  }
  tabs.insertBefore(button, tabs.firstChild)
}

addLocationObserver(init)
init()
