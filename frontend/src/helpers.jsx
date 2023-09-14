import React, {useState} from "react"

export const Check = <i className="fa fa-check green" aria-hidden="true"></i>
export const Info = <i className="fa fa-info hl" aria-hidden="true"></i>
export const X = <i className="fa fa-times red" aria-hidden="true"></i>
export const Warning = <i className={"fa fa-warning yellow"} aria-hidden="true" />

export const Tooltip = ({ tooltipText }) => {
  const [hover, setHover] = useState(false)

  return (
    <span className="tooltip-container" onMouseOver={() => setHover(true)} onMouseOut={() => setHover(false)}>
        <i className="fa fa-question-circle" />
        <div className={`tooltip ${hover ? 'tooltip-show' : ''}`}>
          {tooltipText}
        </div>
      </span>
  )
}

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

  const tooltipText = (
    <>
    <span className="green">Green: </span>
    Exactly {numPossible}
    <br />
    {(Math.ceil(numPossible / 2) !== numPossible) && (
      <>
        <span className="yellow">Yellow: </span>
        Between {Math.ceil(numPossible / 2)} and {numPossible}
        <br />
      </>
    )}
    <span className="red">Red: </span>
    Between 0 and {Math.ceil(numPossible / 2)}
    </>
  )
  return (
    <div className="usage-analysis centered">
      {Icon}
      You used {spellName} <span className={color}>
          {numActual} of {numPossible}
        </span> possible times
        <span className={"usage-tooltip"}>
            <Tooltip tooltipText={tooltipText} />
        </span>
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

  const tooltipText = (
    <>
      <span className="green">Green: </span>
      More than {targetCPM}
      <br />
      <span className="yellow">Yellow: </span>
      Between {Number(targetCPM * 0.8).toFixed(1)} and {targetCPM}
      <br />
      <span className="orange">Orange: </span>
      Between {Number(targetCPM * 0.5).toFixed(1)} and {Number(targetCPM * 0.8).toFixed(1)}
      <br />
      <span className="red">Red: </span>
      Between 0 and {Number(targetCPM * 0.5).toFixed(1)}
    </>
  )
  return (
    <div className="cpm-analysis">
      {Icon}
      You casted {spellName} <span className={color}> {cpm.toFixed(2)} </span> times per minute
      <span className={"cpm-tooltip"}>
          <Tooltip tooltipText={tooltipText} />
      </span>
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

  let tooltip = null

  if (!infoOnly) {
    const tooltipText = (
      <>
        <span className="green">Green: </span>
        More than {Number(maxUptime * 0.9 * 100).toFixed(2)}%
        <br />
        <span className="yellow">Yellow: </span>
        Between {Number(maxUptime * 0.65 * 100).toFixed(2)}% and {Number(maxUptime * 0.9 * 100).toFixed(2)}%
        <br />
        <span className="orange">Orange: </span>
        Between {Number(maxUptime * 0.5 * 100).toFixed(2)}% and {Number(maxUptime * 0.65 * 100).toFixed(2)}%
        <br />
        <span className="red">Red: </span>
        Between 0 and {Number(maxUptime * 0.5 * 100).toFixed(2)}%
      </>
    )
    tooltip = (
      <span className={"uptime-tooltip"}>
          <Tooltip tooltipText={tooltipText} />
      </span>
    )
  }

  return (
    <div className="uptime centered">
      <div>{Icon}</div>
      {spellName} uptime: <span className={color}>{(upTime * 100).toFixed(2)}%</span>
      {tooltip}
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
