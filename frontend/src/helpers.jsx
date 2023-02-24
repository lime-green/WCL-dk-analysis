export const Check = <i className="fa fa-check green" aria-hidden="true"></i>
export const Info = <i className="fa fa-info hl" aria-hidden="true"></i>
export const X = <i className="fa fa-times red" aria-hidden="true"></i>
export const Warning = <i className={"fa fa-warning yellow"} aria-hidden="true" />

export const formatUsage = (numActual, numPossible, spellName, analysisName) => {
  const score = numActual / numPossible
  let Icon = X

  let color = "red"
  if (score === 1) {
    color = "green"
    Icon = Check
  } else if (score >= 0.5) {
    color = "yellow"
  } else if (score > 0) {
    color = "orange"
  }

  return (
    <div className={analysisName}>
      {Icon}
      You used {spellName} <span className={color}>
          {numActual} of {numPossible}
        </span>{" "}
      possible times
    </div>
  )
}

export const formatUpTime = (upTime, spellName, infoOnly=false) => {
  let Icon = X

  let color = "red"
  if (infoOnly) {
    color = "hl"
    Icon = Info
  } else if (upTime > 0.9) {
    color = "green"
    Icon = Check
  } else if (upTime > 0.65) {
    color = "yellow"
    Icon = Warning
  } else if (upTime > 0.5) {
    color = "orange"
  }

  color += " uptime-score"

  return (
    <div className="uptime">
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
    <div>
      {Icon}
      <span>{bool ? positive : negative}</span>
    </div>
  )
}

export const hl = (text) => {
  return <span className="hl">{text}</span>
}
