import {booleanCheck, formatIcon, formatTimestamp, formatUpTime, formatUsage, hl, Info} from "./helpers"


export const GargoyleAnalysis = ({ gargoyle }) => {
  const { windows } = gargoyle

  return (
    <div>
      <h3>Gargoyle</h3>
      <div>
        {formatUsage(gargoyle.num_actual, gargoyle.num_possible, "Gargoyle")}
        <div className="windows">
          {windows.map((window, i) => {
            const numCast = window.num_casts
            const numMelee = window.num_melees

            return (
              <div className="gargoyle-window" key={i}>
                <div className="gargoyle-subheader">
                  <b>Gargoyle {i+1}:</b> ({hl(formatTimestamp(window.start))} - {hl(formatTimestamp(window.end))})
                </div>
                <div>
                  {Info}
                  <span>Damage: {hl(window.damage.toLocaleString())} ({hl(numCast)} casts, {hl(numMelee)} melees)</span>
                </div>
                {window.trinket_uptimes.map((uptime, i) => {
                  const icon = formatIcon(uptime.name, uptime.icon)

                  return (
                    <div key={i}>
                      {formatUpTime(uptime.uptime, <>{icon} {uptime.name}</>)}
                    </div>
                  )
                })}
                <div>
                  {formatUpTime(window.unholy_presence_uptime, "Unholy Presence")}
                </div>
                <div>
                  {formatUpTime(window.bloodlust_uptime, "Bloodlust")}
                </div>
                <div>
                  {formatUpTime(window.hyperspeed_uptime, "Hyperspeed")}
                </div>
                <div>
                  {formatUpTime(window.speed_uptime, "Speed")}
                </div>
                {window.trinket_snapshots.map((snapshot, i) => {
                  const icon = formatIcon(snapshot.name, snapshot.icon)

                  return (
                    <div key={i}>
                      {booleanCheck(snapshot.did_snapshot, <>You snapshotted {icon} {snapshot.name}</>, <>You did not snapshot {icon} {snapshot.name}</>)}
                    </div>
                  )
                })}
                {booleanCheck(window.snapshotted_fc, "You snapshotted Fallen Crusader", "You did not snapshot Fallen Crusader")}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
