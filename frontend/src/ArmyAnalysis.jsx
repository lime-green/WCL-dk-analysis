import {hl, Info, booleanCheck, formatIcon} from "./helpers"

export const ArmyAnalysis = ({army}) => {
  const { snapshots } = army

  return (
    <div>
      <h3>Army of the Dead</h3>
      <div>
        {Info}
        <span>Damage: {hl(army.damage.toLocaleString())}</span>
        {snapshots.map((snapshot, i) => {
          const icon = formatIcon(snapshot.name, snapshot.icon)

          return (
            <div key={i}>
              {booleanCheck(snapshot.did_snapshot, <>You snapshotted {icon} {snapshot.name}</>, <>You did not snapshot {icon} {snapshot.name}</>)}
            </div>
          )
        })}
      </div>
    </div>
  )
}
