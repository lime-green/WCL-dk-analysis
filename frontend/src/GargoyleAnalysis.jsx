import {booleanCheck, formatUpTime, formatUsage, hl, Info} from "./helpers"


export const GargoyleAnalysis = ({ gargoyle }) => {
  const { windows } = gargoyle
  return (
    <div>
      <h3>Gargoyle</h3>
      <div>
        {formatUsage(gargoyle.num_actual, gargoyle.num_possible, "Gargoyle", "gargoyle")}
        <div className="windows">
          {windows.map((window, i) => {
            const numCast = window.num_casts
            const numMelee = window.num_melees

            return (
              <div className="gargoyle-window" key={i}>
                <div>
                  {formatUpTime(window.unholy_presence_uptime, "Unholy Presence")}
                </div>
                <div>
                  {formatUpTime(window.bloodlust_uptime, "Bloodlust")}
                </div>
                {booleanCheck(window.snapshotted_fc, "You snapshotted Fallen Crusader", "You did not snapshot Fallen Crusader")}
                {booleanCheck(window.snapshotted_greatness, "You snapshotted Greatness", "You did not snapshot Greatness")}
                {booleanCheck(window.used_hyperspeed, "You used Hyperspeed Accelerators", "You did not use Hyperspeed Accelerators")}
                {booleanCheck(window.used_speed_potion, "You used Speed Potion", "You did not use Speed Potion")}
                <div>
                  {Info}
                  <span>Damage: {hl(window.damage.toLocaleString())} ({hl(numCast)} casts, {hl(numMelee)} melees)</span>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
