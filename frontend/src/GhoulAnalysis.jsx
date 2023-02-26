import {booleanCheck, formatUpTime, formatCPM, hl, Info} from "./helpers"

export const GhoulAnalysis = ({ghoul}) => {
  return (
    <div>
      <h3>Ghoul</h3>
      <div>
        {Info}
        <span>Damage: {hl(ghoul.damage.toLocaleString())}</span>
      </div>
      {formatUpTime(ghoul.melee_uptime, "Melee")}
      {formatUpTime(ghoul.uptime, "Alive")}
      {formatCPM(ghoul.claw_cpm, ghoul.claw_cpm_possible, "Claw")}
      {booleanCheck(ghoul.num_gnaws === 0, "You did not use Gnaw", `You used Gnaw ${ghoul.num_gnaws} times`)}
    </div>
  )
}
