import React, {useCallback, useContext, useState} from "react";
import {LogAnalysisContext} from "./LogAnalysisContext.jsx";

import BloodRune from "./assets/blood_rune.webp";
import FrostRune from "./assets/frost_rune.webp";
import UnholyRune from "./assets/unholy_rune.webp";
import DeathRune from "./assets/death_rune.webp";
import { ArmyAnalysis } from "./ArmyAnalysis.jsx"
import { GargoyleAnalysis } from "./GargoyleAnalysis"
import { GhoulAnalysis } from "./GhoulAnalysis.jsx"
import { formatCPM, formatIcon, formatTimestamp, formatUpTime, formatUsage } from "./helpers"

const formatRune = (rune, i) => {
  const src = {
    Blood: BloodRune,
    Frost: FrostRune,
    Unholy: UnholyRune,
    Death: DeathRune,
  }[rune.name];
  const className = rune.is_available ? "rune rune-available" : "rune rune-cd";

  return (
    <img
      key={i}
      className={className}
      src={src}
      title={rune.name}
      alt={rune.name}
      width={14}
    />
  );
};

const ABILITY_TYPES = new Set([0, 1, 4, 16, 32]);

const getAbilityTypeClass = (abilityType) => {
  if (ABILITY_TYPES.has(abilityType)) {
    return `ability-name ability-type-${abilityType}`;
  }
  return "ability-name ability-type-unknown";
};

const formatRanking = (ranking) => {
  let color = "grey";

  if (ranking === 100) {
    color = "gold";
  } else if (ranking >= 99) {
    color = "pink";
  } else if (ranking >= 95) {
    color = "orange";
  } else if (ranking >= 75) {
    color = "purple";
  } else if (ranking >= 50) {
    color = "blue";
  }

  return <span className={color}>{ranking}</span>;
};

const Summary = () => {
  const analysis = useContext(LogAnalysisContext);

  const formatGCDLatency = useCallback((gcdLatency, infoOnly) => {
    const averageLatency = gcdLatency.average_latency;

    let color = "green";

    if (infoOnly) {
      color = "hl"
    } else if (averageLatency > 200) {
      color = "red";
    } else if (averageLatency > 100) {
      color = "yellow";
    }

    return (
      <div className={"gcd-latency"}>
        <i className="fa fa-clock-o hl" aria-hidden="true"></i>
        Your average GCD delay was{" "}
        <span className={color}>{averageLatency.toFixed(2)} ms</span>
      </div>
    );
  }, []);

  const formatDiseases = useCallback((diseasesDropped) => {
    const numDiseasesDropped = diseasesDropped.num_diseases_dropped;

    if (numDiseasesDropped > 0) {
      return (
        <div className={"diseases-dropped"}>
          <i className="fa fa-times red" aria-hidden="true"></i>
          You dropped diseases{" "}
          <span className={"hl"}>{numDiseasesDropped}</span> times on boss
          targets
        </div>
      );
    } else {
      return (
        <div className={"diseases-dropped"}>
          <i className="fa fa-check green" aria-hidden="true"></i>
          Nice work, you didn't drop diseases on boss targets before the last 10
          seconds of the fight!
        </div>
      );
    }
  }, []);

  const formatFlask = useCallback((flaskUsage) => {
    const hasFlask = flaskUsage.has_flask;

    if (hasFlask) {
      return (
        <div className={"flask-usage"}>
          <i className="fa fa-check green" aria-hidden="true"></i>
          You had a Flask of Endless Rage
        </div>
      );
    }
    return (
      <div className={"flask-usage"}>
        <i className="fa fa-times red" aria-hidden="true"></i>
        You did not have a Flask of Endless Rage
      </div>
    );
  }, []);

  const formatRuneDrift = useCallback((runeDrift, infoOnly) => {
    const runeDriftMs = runeDrift.rune_drift_ms;

    let color = "green";

    if (infoOnly) {
      color = "hl"
    } else if (runeDriftMs > 10000) {
      color = "red";
    } else if (runeDriftMs > 5000) {
      color = "yellow";
    }

    const runeDriftSeconds = runeDriftMs / 1000;

    return (
      <div className={"rune-drift"}>
        <i className="fa fa-clock-o hl" aria-hidden="true"></i>
        You drifted runes by a total of{" "}
        <span className={color}>{runeDriftSeconds.toFixed(2)} seconds</span>
      </div>
    );
  }, []);

  const formatKillingMachine = useCallback((killingMachine) => {
    const averageLatency = killingMachine.avg_latency;
    const averageLatencySeconds = averageLatency / 1000;
    const numUsed = killingMachine.num_used;
    const numTotal = killingMachine.num_total;
    let color = "green";

    if (averageLatency > 2500) {
      color = "red";
    } else if (averageLatency > 2000) {
      color = "yellow";
    }

    return (
      <div className={"killing-machine"}>
        <i className="fa fa-clock-o hl" aria-hidden="true"></i>
        You used{" "}
        <span className={"hl"}>
          {numUsed} of {numTotal}
        </span>{" "}
        Killing Machine procs with an average delay of{" "}
        <span className={color}>
          {averageLatencySeconds.toFixed(2)} seconds
        </span>
      </div>
    );
  }, []);

  const formatHowlingBlast = useCallback((howlingBlast) => {
    const numBadUsages = howlingBlast.num_bad_usages;

    if (numBadUsages === 0) {
      return (
        <div className={"howling-blast"}>
          <i className="fa fa-check green" aria-hidden="true"></i>
          You always used Howling Blast with Rime or on 3+ targets
        </div>
      );
    }
    return (
      <div className={"howling-blast"}>
        <i className="fa fa-times red" aria-hidden="true"></i>
        You used Howling Blast <span className={"hl"}>{numBadUsages}</span>{" "}
        times without Rime or on less than 3 targets
      </div>
    );
  }, []);

  const formatPotions = useCallback((potions) => {
    const potionsUsed = potions.potions_used;
    const total = potionsUsed > 2 ? potionsUsed : 2

    if (potionsUsed >= 2) {
      return (
        <div className={"potions"}>
          <i className="fa fa-check green" aria-hidden="true"></i>
          You used <span className={"hl"}>{potionsUsed} of {total}</span> Potions (Speed or Indestructible)
        </div>
      );
    }
    return (
      <div className={"potions"}>
        <i className="fa fa-times red" aria-hidden="true"></i>
        You used <span className={"hl"}>{potionsUsed} of 2</span> Potions (Speed or Indestructible)
      </div>
    );
  }, []);

  const formatUA = useCallback((UA) => {
    const numActual = UA.num_actual;
    const numPossible = UA.num_possible;
    const windows = UA.windows;

    const formatWindows = () => {
      return (
        <div className={"windows"}>
          {windows.map((window, i) => {
            let icon = <i className="fa fa-times red" aria-hidden="true" />;
            if (window.num_actual === window.num_possible) {
              icon = <i className="fa fa-check green" aria-hidden="true" />;
            }

            return (
              <div key={i} className={"window"}>
                {icon}
                Hit{" "}
                <span className={"hl"}>
                  {window.num_actual} of {window.num_possible}
                </span>{" "}
                Obliterates {window.with_erw ? "(with ERW) " : ""}
              </div>
            );
          })}
        </div>
      );
    };

    let icon = <i className="fa fa-times red" aria-hidden="true" />;
    if (numActual === numPossible) {
      icon = <i className="fa fa-check green" aria-hidden="true" />;
    }
    return (
      <div className={"unbreakable-armor-analysis"}>
        {icon}
        You used Unbreakable Armor{" "}
        <span className={"hl"}>
          {numActual} of {numPossible}
        </span>{" "}
        possible times. Within those windows:
        {formatWindows()}
      </div>
    );
  }, []);

  const formatRunicPower = useCallback((runicPower) => {
    const overcapTimes = runicPower.overcap_times
    const overcapSum = runicPower.overcap_sum
    const gainedSum = runicPower.gained_sum

    return (
      <div className={"runic-power-analysis"}>
        <div>
          <i className="fa fa-info hl" aria-hidden="true"></i>
          You gained a total of <span className={"hl"}>{gainedSum}</span> Runic Power using AMS
        </div>
        <div>
          <i className="fa fa-info hl" aria-hidden="true"></i>
          You over-capped Runic Power <span className={"hl"}>
            {overcapTimes}
          </span>{" "}
          times for a total of
          <span className={"hl"}> {overcapSum} RP</span> wasted
        </div>
      </div>
    );
  }, []);

  const formatRime = useCallback(rime => {
    const numTotal = rime.num_total
    const numUsed = rime.num_used
    return (
      <div className={"rime-analysis"}>
        <i className="fa fa-info hl" aria-hidden="true"></i>
        You used your Rime procs <span className={"hl"}>
          {numUsed} of {numTotal}
        </span>{" "}
        times
      </div>
    )
  }, [])

  const Tooltip = ({ tooltipText }) => {
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

  const formatScore = useCallback(score => {
    let color = "red"
    if (score > 0.8) {
      color = "green"
    } else if (score > 0.65) {
      color = "yellow"
    } else if (score > 0.5) {
      color = "orange"
    }

    return (
      <h2>
        Analysis score: <span className={`total-score ${color}`}>{(score * 100).toFixed(2)}</span>
        <span className={"total-score-tooltip"}>
          <Tooltip tooltipText="A score of how well you did on this fight, based upon Speed, Rotation and Misc. metrics, each weighted differently. Range is 0-100."/>
        </span>
      </h2>
    )
  }, [])

  if (analysis.isLoading || analysis.error) {
    return;
  }

  const data = analysis.data;
  const fight = data.fight_metadata;

  let fightRanking, playerRanking, dps
  if (Object.keys(fight.rankings).length !== 0) {
    fightRanking = fight.rankings.fight_ranking?.speed_percentile || "n/a"
    playerRanking = fight.rankings.player_ranking?.rank_percentile || "n/a"
    dps = Math.round(fight.rankings.player_ranking?.dps) || "n/a"
  } else {
    fightRanking = "n/a"
    playerRanking = "n/a"
    dps = "n/a"
  }
  const summary = data.analysis;
  const isUnholy = data.spec === "Unholy"
  const showSpeed = data.show_speed

  return (
    <div className={"analysis-summary"}>
      <div className={"fight-summary"}>
        <h2>{fight.source}</h2>
        <div className={"summary-line"}>
          Encounter: <span className={"hl"}>{fight.encounter}</span>
        </div>
        <div className={"summary-line"}>
          DPS:{" "}
          <span className={"hl"}>
            {dps}
          </span>{" "}
          ({formatRanking(playerRanking)})
        </div>
        <div className={"summary-line"}>
          Duration:{" "}
          <span className={"hl"}>{formatTimestamp(fight.duration)}</span> (
          {formatRanking(fightRanking)})
        </div>
      </div>
      <div className={"total-score-div"}>
        {formatScore(summary.analysis_scores.total_score)}
      </div>
      <div className="fight-analysis">
        {
          showSpeed && (
            <div className="analysis-section fight-analysis">
              <h3>Speed</h3>
              {formatGCDLatency(summary.gcd_latency, isUnholy)}
              {formatRuneDrift(summary.rune_drift, isUnholy)}
              {summary.killing_machine && formatKillingMachine(summary.killing_machine)}
            </div>
          )
        }
        <div className="analysis-section">
          <h3>Rotation</h3>
          {summary.obliterate && formatCPM(summary.obliterate.cpm, summary.obliterate.target_cpm, "Obliterate")}
          {summary.dnd !== undefined && formatUpTime(summary.dnd.uptime, "Death and Decay", false, summary.dnd.max_uptime)}
          {summary.desolation_uptime !== undefined && formatUpTime(summary.desolation_uptime, "Desolation")}
          {summary.sigil_uptime !== undefined && formatUpTime(summary.sigil_uptime, summary.sigil_name, false, summary.sigil_max_uptime)}
          {summary.ghoul_frenzy_uptime !== undefined && formatUpTime(summary.ghoul_frenzy_uptime, "Ghoul Frenzy", false, summary.ghoul_frenzy_max_uptime)}
          {summary.t9_uptime !== undefined && formatUpTime(summary.t9_uptime, "Unholy Might (T9 2p)", false, summary.t9_max_uptime)}
          {summary.melee_uptime !== undefined && formatUpTime(summary.melee_uptime, "Melee")}
          {summary.unbreakable_armor && formatUA(summary.unbreakable_armor)}
          {summary.blood_plague_uptime !== undefined && formatUpTime(summary.blood_plague_uptime, "Blood Plague")}
          {summary.frost_fever_uptime !== undefined && formatUpTime(summary.frost_fever_uptime, "Frost Fever")}
          {summary.blood_presence_uptime !== undefined && formatUpTime(summary.blood_presence_uptime, "Blood Presence (outside of Gargoyle)")}
          {summary.blood_tap_usages !== undefined && formatUsage(summary.blood_tap_usages, summary.blood_tap_max_usages, "Blood Tap")}
          {summary.bone_shield_uptime !== undefined && formatUpTime(summary.bone_shield_uptime, "Bone Shield", true)}
          {summary.diseases_dropped && formatDiseases(summary.diseases_dropped)}
          {summary.raise_dead_usage && formatUsage(summary.raise_dead_usage.num_usages, summary.raise_dead_usage.possible_usages, "Raise Dead")}
          {summary.howling_blast_bad_usages && formatHowlingBlast(summary.howling_blast_bad_usages)}
          {summary.runic_power && formatRunicPower(summary.runic_power)}
          {summary.rime && formatRime(summary.rime)}
        </div>
        {summary.gargoyle && (
          <div className="analysis-section">
            <GargoyleAnalysis gargoyle={summary.gargoyle} />
          </div>
        )}
        {summary.ghoul && (
          <div className="analysis-section">
            <GhoulAnalysis ghoul={summary.ghoul} />
          </div>
        )}
        {summary.army && (
          <div className="analysis-section">
            <ArmyAnalysis army={summary.army} />
          </div>
        )}
        <div className="analysis-section">
          <h3>Miscellaneous</h3>
          {summary.trinket_usages && summary.trinket_usages.map((trinket, index) => (
            <div key={index}>
              {formatUsage(
                trinket.num_actual,
                trinket.num_possible,
                <>{formatIcon(trinket.name, trinket.icon)} {trinket.name}</>,
              )}
            </div>
          ))}
          {summary.hyperspeed && formatUsage(
            summary.hyperspeed.num_actual,
            summary.hyperspeed.num_possible,
            "Hyperspeed Accelerators",
          )}
          {summary.potion_usage && formatPotions(summary.potion_usage)}
          {summary.bomb_usage && formatUsage(
            summary.bomb_usage.thermal_actual,
            summary.bomb_usage.thermal_possible,
            "Global Thermal Sapper Charge",
          )}
          {summary.bomb_usage && formatUsage(
            summary.bomb_usage.saronite_actual,
            summary.bomb_usage.saronite_possible,
            "Saronite Bomb",
          )}
          {summary.flask_usage && formatFlask(summary.flask_usage)}
        </div>
      </div>
    </div>
  );
};

export const Analysis = () => {
  const analysis = useContext(LogAnalysisContext);

  const formatEvent = useCallback((event, showRunes, showProcs, i) => {
    const abilityIcon = event.ability_icon;
    const icon = (
      <img
        src={abilityIcon}
        title={event.ability}
        alt={event.ability}
        width={20}
      />
    );
    const offset = event.gcd_offset;
    let ability = event.ability;
    let timestamp = <span>{formatTimestamp(event.timestamp)}</span>;
    let runicPower = String(Math.floor(event.runic_power / 10)).padStart(
      3,
      " "
    );

    let abilityTdClass = "";
    let abilityDivClass = "ability";
    let rowClass = "";

    if (event.runic_power_waste) {
      const runic_power_waste = Math.floor(event.runic_power_waste / 10);
      runicPower = (
        <>
          {runicPower} <span className={"red"}>(+{runic_power_waste})</span>
        </>
      );
    }

    if (event.type === "removedebuff") {
      abilityTdClass = "debuff-drops";
      ability = `${ability} drops on ${event.target}`;
    }

    if (event.type === "removebuff") {
      abilityTdClass = "buff-drops";
      ability = `${ability} ends`;
    }

    if (event.is_miss) {
      rowClass = "ability-miss";
      ability = (
        <>
          {ability}{" "}
          <span className={"red"}>({event.hit_type.toLowerCase()})</span>
        </>
      );
    }

    if (!event.is_core_cast) {
      abilityDivClass += " filler-cast";
    }

    const hasUnholyPresence = event.buffs.some((buff) => buff.ability === "Unholy Presence")
    const assumedGCD = hasUnholyPresence ? 1000 : 1500

    if (event.has_gcd && offset) {
      let color;
      if (offset - assumedGCD > 500) {
        color = "red";
      } else if (offset - assumedGCD > 100) {
        color = "yellow";
      } else {
        color = "green";
      }

      timestamp = (
        <span>
          {formatTimestamp(event.timestamp)}{" "}
          <span className={color}>
            (+{formatTimestamp(event.gcd_offset, false)})
          </span>
        </span>
      );
    }

    const formatBuff = (buff) => {
      return (
        <img
          key={buff.abilityGameID}
          src={buff.ability_icon}
          title={buff.ability}
          alt={buff.ability}
          width={20}
        />
      );
    };

    let procsUsed = [];
    event.buffs.forEach((buff) => {
      if (event.consumes_km && buff.ability === "Killing Machine") {
        procsUsed.push(buff);
      }
      if (event.consumes_rime && buff.ability === "Rime") {
        procsUsed.push(buff);
      }
    });

    const formatRuneDrift = (rune_grace_wasted) => {
      if (!rune_grace_wasted || rune_grace_wasted === 0) {
        return null;
      }

      let color = "yellow";
      if (rune_grace_wasted > 1500) {
        color = "red";
      } else if (rune_grace_wasted > 1000) {
        color = "orange";
      }
      return (
        <span className={color}>
          +{formatTimestamp(rune_grace_wasted, false)}
        </span>
      );
    };

    return (
      <tr className={rowClass} key={i}>
        <td className={"timestamp"}>{timestamp}</td>
        <td className={abilityTdClass}>
          <div className={abilityDivClass}>
            {icon}{" "}
            <span className={getAbilityTypeClass(event.ability_type)}>
              {ability}
            </span>
          </div>
        </td>
        <td>
          <div className={"runic-power"}>{runicPower}</div>
        </td>
        {showRunes ? (
          <>
            <td>
              <div className={"runes"}>
                {event.runes_before.map(formatRune)}
              </div>
              {event.modifies_runes && (
                <div className={"runes"}>{event.runes.map(formatRune)}</div>
              )}
            </td>
            <td>{formatRuneDrift(event.rune_grace_wasted)}</td>
          </>
        ) : null}
        <td>
          <div className={"buffs"}>{event.buffs.map(formatBuff)}</div>
        </td>
        {showProcs &&
          <td>
            <div className={"procs-used"}>{procsUsed.map(formatBuff)}</div>
          </td>
        }
      </tr>
    );
  }, []);

  if (analysis.error) {
    return <>Error: {analysis.error}</>;
  }

  if (analysis.isLoading) {
    return (
      <div className={"fa-2x"}>
        <i className="fa fa-spinner fa-spin"></i>
      </div>
    );
  }

  const data = analysis.data;
  const events = data.events;
  const summary = data.analysis;

  const runeWarning = () => {
    const warning = <i className={"fa fa-warning yellow"} />;
    if (summary.has_rune_spend_error) {
      return (
        <span>{warning} The runes for this fight could not be guessed</span>
      );
    }
    return <span>{warning} Runes shown are a best-effort approximation</span>;
  };

  return (
    <>
      <a rel="noreferrer" href={window.location.href} target={"_blank"}>
        <i className="fa fa-external-link" aria-hidden="true" />
      </a>
      <Summary />
      {runeWarning()}
      <div className={"events-table"}>
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Ability</th>
              <th>RP</th>
              {summary.has_rune_spend_error ? null : (
                <>
                  <th>Runes</th>
                  <th>Rune Drift</th>
                </>
              )}
              <th>Buffs</th>
              {data.show_procs && <th>Procs Used</th>}
            </tr>
          </thead>
          <tbody>
            {events.map((event, i) =>
              formatEvent(event, !summary.has_rune_spend_error, data.show_procs, i)
            )}
          </tbody>
        </table>
      </div>
    </>
  );
};
