export const Check = <i className="fa fa-check green" aria-hidden="true"></i>
export const Info = <i className="fa fa-info hl" aria-hidden="true"></i>
export const X = <i className="fa fa-times red" aria-hidden="true"></i>
export const Warning = <i className={"fa fa-warning yellow"} aria-hidden="true" />

export const formatUsage = (numActual, numPossible, spellName) => {
  const score = numActual / numPossible
  let Icon = X

  let color = "red"
  if (score >= 1 || numPossible === 0) {
    color = "green"
    Icon = Check
  } else if (score >= 0.5) {
    color = "yellow"
    Icon = Warning
  } else if (score > 0) {
    color = "orange"
  }

  return (
    <div className="usage-analysis centered">
      {Icon}
      You used {spellName} <span className={color}>
          {numActual} of {numPossible}
        </span> possible times
    </div>
  )
}

export const formatCPM = (cpm, targetCPM, spellName) => {
  const score = cpm / targetCPM
  let Icon = X

  let color = "red"
  if (score >= 1) {
    color = "green"
    Icon = Check
  } else if (score >= 0.8) {
    color = "yellow"
    Icon = Warning
  } else if (score > 0.5) {
    color = "orange"
  }

  return (
    <div className="usage-analysis">
      {Icon}
      You casted {spellName} <span className={color}> {cpm.toFixed(2)} </span> times per minute
    </div>
  )
}

export const formatUpTime = (upTime, spellName, infoOnly=false, maxUptime = 1.0) => {
  let Icon = X
  const uptimePercent = upTime / maxUptime

  let color = "red"
  if (infoOnly) {
    color = "hl"
    Icon = Info
  } else if (uptimePercent > 0.9) {
    color = "green"
    Icon = Check
  } else if (uptimePercent > 0.65) {
    color = "yellow"
    Icon = Warning
  } else if (uptimePercent > 0.5) {
    color = "orange"
  }

  color += " uptime-score"

  return (
    <div className="uptime centered">
      <div>{Icon}</div>
      {spellName} uptime: <span className={color}>{(upTime * 100).toFixed(2)}%</span>
    </div>
  )
}

export const booleanCheck = (bool, positive, negative) => {
  let Icon = X

  if (bool) {
    Icon = Check
  }

  return (
    <div className={"centered"}>
      {Icon}
      <div className={"centered"}>{bool ? positive : negative}</div>
    </div>
  )
}

export const hl = (text) => {
  return <span className="hl">{text}</span>
}

export const formatIcon = (name, href) => {
  if (!href) {
    return null
  }

  return (
    <img
      className={"icon"}
      src={href}
      title={name}
      alt={name}
      width={20}
    />
  );
}

export const formatTimestamp = (milliSeconds, zeroPad = true) => {
  let seconds = Math.floor(milliSeconds / 1000);
  let minutes = Math.floor(seconds / 60);
  let extraSeconds = seconds % 60;

  if (zeroPad) {
    minutes = String(minutes).padStart(2, "0");
  }

  if (zeroPad) {
    extraSeconds = String(extraSeconds).padStart(2, "0");
  }

  let extraMilliseconds = String(milliSeconds % 1000).padStart(3, "0");

  if (zeroPad) {
    return `${minutes}:${extraSeconds}.${extraMilliseconds}`;
  }

  return `${extraSeconds}.${extraMilliseconds}`;
};
