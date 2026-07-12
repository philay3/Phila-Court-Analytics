/**
 * Real charge-roster seed data for the ref.* layer (Task 22.2).
 *
 * Sourced from PUBLIC Pennsylvania statute references (Pa. C.S., primarily
 * Titles 18 / 35 / 75, plus Title 23 § 6114 and Title 62 § 1407 which also
 * appear at or above the approved coverage floor). Every entry carries a public
 * statute code and a public-statute-phrasing display name.
 *
 * ALIAS SOURCING BASIS (roster gate, Decision 3): every alias is either
 * public statute phrasing OR a STANDARDIZED CPCMS charge-description string —
 * the Commonwealth's own charge dictionary, verifiable against public UJS/CPCMS
 * references independently of our corpus. Aliases are NEVER free text and NEVER
 * docket-specific content; they exist only to let the matcher fold the observed
 * standardized offense description onto the entry.
 *
 * Statute codes are written in the parenthetical subsection form
 * (e.g. `18 § 6106(a)(1)`); the 22.2 statute canonicalizer folds this to the
 * same key as the CPCMS `§§ A1` docket form, so both compare equal.
 *
 * Coexistence (Sprint 5 SD 8): these rows coexist with the Sprint 2 demo charge
 * ROWS, which are never modified. No roster row duplicates a demo row's
 * canonical statute code. Per the roster gate (Decision 4), the roster seed
 * ADDITIVELY attaches standardized-CPCMS aliases to demo rows via
 * ref.charge_aliases (see DEMO_ALIAS_ADDITIONS) — this leaves the demo
 * ref.normalized_charges rows untouched while letting demo identities absorb the
 * observed corpus offense text (e.g. controlled-substance possession, retail
 * theft) as clean single-entity alias matches. The seed asserts (fail-loud) that
 * no roster slug collides with the demo-seed slug registry.
 *
 * Grades are intentionally absent (grading varies by circumstance), matching the
 * demo-seed convention.
 */

import type { ChargeSeed } from './reference-data.js';

/**
 * Additive standardized-CPCMS aliases attached to EXISTING Sprint 2 demo rows
 * (keyed by demo slug), inserted into ref.charge_aliases by the roster seed
 * (Decision 4). The demo ref.normalized_charges rows are never touched. Each
 * alias resolves a class of corpus offense text that the demo identity owns but
 * whose statute/text did not previously produce a clean single-entity match —
 * applied only where it converts an unmatched/statute-only case into a clean
 * alias match without creating new ambiguity or conflict:
 *
 * - `possession-controlled-substance` (35 § 780-113(a)(16)) absorbs the CPCMS
 *   possession description, resolving the bare-`35 § 780-113` + possession-text
 *   class (previously unmatched) as a clean alias match.
 * - `retail-theft` (18 § 3929) absorbs the CPCMS retail-theft "take of
 *   merchandise" description, so both the bare and (a)(1) retail-theft charges
 *   resolve to the demo row (this replaced a statute-only real roster entry).
 */
export interface DemoAliasAddition {
  slug: string;
  aliases: readonly string[];
}

export const DEMO_ALIAS_ADDITIONS: readonly DemoAliasAddition[] = [
  {
    slug: 'possession-controlled-substance',
    aliases: ['Int Poss Contr Subst By Per Not Reg'],
  },
  {
    slug: 'retail-theft',
    aliases: ['Retail Theft-Take Mdse'],
  },
];

export const CHARGE_ROSTER_SEEDS: readonly ChargeSeed[] = [
  // --- Controlled substances (Title 35) --------------------------------------
  {
    slug: 'pwid-controlled-substance',
    displayName: 'Manufacture, Delivery, or Possession With Intent (PWID)',
    statuteCode: '35 § 780-113(a)(30)',
    aliases: ['Manufacture, Delivery, or Possession With Intent to Manufacture or Deliver'],
  },
  {
    slug: 'use-poss-drug-paraphernalia',
    displayName: 'Use or Possession of Drug Paraphernalia',
    statuteCode: '35 § 780-113(a)(32)',
    aliases: ['Use/Poss Of Drug Paraph'],
  },

  // --- Firearms (Title 18, Chapter 61) ---------------------------------------
  {
    slug: 'firearms-carried-without-license',
    displayName: 'Firearms Not to Be Carried Without a License',
    statuteCode: '18 § 6106(a)(1)',
    aliases: ['Firearms Not To Be Carried W/O License'],
  },
  {
    slug: 'possession-firearm-prohibited',
    displayName: 'Possession of Firearm Prohibited',
    statuteCode: '18 § 6105(a)(1)',
    aliases: ['Possession Of Firearm Prohibited'],
  },
  {
    slug: 'carry-firearms-public-philadelphia',
    displayName: 'Carrying Firearms on Public Streets in Philadelphia',
    statuteCode: '18 § 6108',
    aliases: ['Carry Firearms Public In Phila'],
  },
  {
    slug: 'firearm-altered-manufacturer-number',
    displayName: 'Possession of Firearm With Altered Manufacturer Number',
    statuteCode: '18 § 6110.2(a)',
    aliases: ['Posses Firearm W/Manufacturer Number Altered, Etc'],
  },
  {
    slug: 'firearm-false-written-statement',
    displayName: 'Firearms — Materially False Written Statement',
    statuteCode: '18 § 6111(g)(4)(ii)',
    aliases: ['Materially false written statement - purchase, delivery, transfer of firearm'],
  },
  {
    slug: 'firearm-sale-ineligible-transferee',
    displayName: 'Firearms — Sale to Ineligible Transferee',
    statuteCode: '18 § 6111(g)(2)',
    aliases: ['Penalties - Sales to Ineligible Transferee'],
  },
  {
    slug: 'firearm-sales-penalties',
    displayName: 'Firearms — Unlawful Sale',
    statuteCode: '18 § 6111(g)(1)',
    aliases: ['Penalties - Sales of Firearms'],
  },
  {
    slug: 'possession-firearm-by-minor',
    displayName: 'Possession of Firearm by Minor',
    statuteCode: '18 § 6110.1(a)',
    aliases: ['Possession Of Firearm By Minor'],
  },
  {
    slug: 'unlawful-contact-with-minor',
    displayName: 'Unlawful Contact With Minor',
    statuteCode: '18 § 6318(a)(1)',
    aliases: ['Unlawful Contact With Minor - Sexual Offenses'],
  },
  {
    slug: 'child-pornography',
    displayName: 'Child Pornography',
    statuteCode: '18 § 6312(d)',
    aliases: ['Child Pornography'],
  },

  // --- Possessing instruments of crime ---------------------------------------
  {
    slug: 'possess-instrument-of-crime',
    displayName: 'Possessing Instruments of Crime',
    statuteCode: '18 § 907(a)',
    aliases: ['Poss Instrument Of Crime W/Int'],
  },

  // --- Assault / endangerment ------------------------------------------------
  {
    slug: 'aggravated-assault-sbi',
    displayName: 'Aggravated Assault — Serious Bodily Injury',
    statuteCode: '18 § 2702(a)(1)',
    aliases: [
      'Aggravated Assault - Attempts to cause SBI or causes injury with extreme indifference',
    ],
  },
  {
    slug: 'aggravated-assault-deadly-weapon',
    displayName: 'Aggravated Assault — Bodily Injury With Deadly Weapon',
    statuteCode: '18 § 2702(a)(4)',
    aliases: ['Aggravated Assault - Attempts to cause or causes BI with deadly weapon'],
  },
  {
    slug: 'aggravated-assault-designated-individuals',
    displayName: 'Aggravated Assault — Bodily Injury to Designated Individuals',
    statuteCode: '18 § 2702(a)(3)',
    aliases: ['Aggravated Assault - Attempts to cause or causes BI to designated individuals'],
  },
  {
    slug: 'aggravated-assault-fear-sbi-designated',
    displayName:
      'Aggravated Assault — Fear of Imminent Serious Bodily Injury to Designated Individuals',
    statuteCode: '18 § 2702(a)(6)',
    aliases: ['Aggravated Assault - Fear of Imminent SBI designated individuals'],
  },
  {
    slug: 'recklessly-endangering',
    displayName: 'Recklessly Endangering Another Person',
    statuteCode: '18 § 2705',
    aliases: ['Recklessly Endangering Another Person'],
  },
  {
    slug: 'terroristic-threats',
    displayName: 'Terroristic Threats',
    statuteCode: '18 § 2706(a)(1)',
    aliases: ['Terroristic Threats W/ Int To Terrorize Another'],
  },
  {
    slug: 'strangulation',
    displayName: 'Strangulation',
    statuteCode: '18 § 2718(a)(1)',
    aliases: ['Strangulation - Applying Pressure to Throat or Neck'],
  },
  {
    slug: 'discharge-firearm-occupied-structure',
    displayName: 'Discharge of a Firearm Into an Occupied Structure',
    statuteCode: '18 § 2707.1(a)',
    aliases: ['Discharge Of A Firearm Into Occupied Structure'],
  },
  {
    slug: 'unlawful-restraint',
    displayName: 'Unlawful Restraint — Risk of Serious Bodily Injury',
    statuteCode: '18 § 2902(a)(1)',
    aliases: ['Unlawful Restraint/ Serious Bodily Injury'],
  },

  // --- Homicide --------------------------------------------------------------
  {
    slug: 'murder',
    displayName: 'Murder',
    statuteCode: '18 § 2502',
    aliases: ['Murder'],
  },
  {
    slug: 'murder-first-degree',
    displayName: 'Murder of the First Degree',
    statuteCode: '18 § 2502(a)',
    aliases: ['Murder Of The First Degree'],
  },
  {
    slug: 'murder-third-degree',
    displayName: 'Murder of the Third Degree',
    statuteCode: '18 § 2502(c)',
    aliases: ['Murder Of The Third Degree'],
  },
  {
    slug: 'voluntary-manslaughter',
    displayName: 'Voluntary Manslaughter',
    statuteCode: '18 § 2503(b)',
    aliases: ['Voluntary Mans - Unreasonable Belief'],
  },
  {
    slug: 'involuntary-manslaughter',
    displayName: 'Involuntary Manslaughter',
    statuteCode: '18 § 2504(a)',
    aliases: ['Involuntary Manslaughter'],
  },
  {
    slug: 'homicide-by-vehicle',
    displayName: 'Homicide by Vehicle',
    statuteCode: '75 § 3732(a)',
    aliases: ['Homicide By Vehicle'],
  },

  // --- Robbery ---------------------------------------------------------------
  {
    slug: 'robbery-serious-bodily-injury',
    displayName: 'Robbery — Inflict Serious Bodily Injury',
    statuteCode: '18 § 3701(a)(1)(i)',
    aliases: ['Robbery-Inflict Serious Bodily Injury'],
  },
  {
    slug: 'robbery-threat-serious-injury',
    displayName: 'Robbery — Threat of Immediate Serious Injury',
    statuteCode: '18 § 3701(a)(1)(ii)',
    aliases: ['Robbery-Threat Immed Ser Injury'],
  },
  {
    slug: 'robbery-threat-bodily-injury',
    displayName: 'Robbery — Threat of Immediate Bodily Injury',
    statuteCode: '18 § 3701(a)(1)(iv)',
    aliases: ['Robbery-Inflict Threat Imm Bod Inj'],
  },
  {
    slug: 'robbery-take-property-by-force',
    displayName: 'Robbery — Take Property From Another by Force',
    statuteCode: '18 § 3701(a)(1)(v)',
    aliases: ['Robbery-Take Property Fr Other/Force'],
  },
  {
    slug: 'robbery-financial-institution',
    displayName: 'Robbery — Demand Money From a Financial Institution',
    statuteCode: '18 § 3701(a)(1)(vi)',
    aliases: ['Robbery - demand money from financial institution'],
  },
  {
    slug: 'robbery-of-motor-vehicle',
    displayName: 'Robbery of Motor Vehicle',
    statuteCode: '18 § 3702(a)',
    aliases: ['Robbery Of Motor Vehicle'],
  },

  // --- Burglary / criminal trespass ------------------------------------------
  {
    slug: 'burglary-not-overnight-no-person',
    displayName: 'Burglary — Not Adapted for Overnight Accommodation, No Person Present',
    statuteCode: '18 § 3502(a)(4)',
    aliases: ['Burglary - Not Adapted for Overnight Accommodation, No Person Present'],
  },
  {
    slug: 'burglary-overnight-person-present-bi',
    displayName: 'Burglary — Overnight Accommodations, Person Present, Bodily Injury Crime',
    statuteCode: '18 § 3502(a)(1)(i)',
    aliases: ['Burglary - Overnight Accommodations; Person Present, Bodily Injury Crime'],
  },
  {
    slug: 'burglary-overnight-person-present',
    displayName: 'Burglary — Overnight Accommodations, Person Present',
    statuteCode: '18 § 3502(a)(1)(ii)',
    aliases: ['Burglary - Overnight Accommodations; Person Present'],
  },
  {
    slug: 'criminal-trespass-break-into-structure',
    displayName: 'Criminal Trespass — Break Into Structure',
    statuteCode: '18 § 3503(a)(1)(ii)',
    aliases: ['Crim Tres-Break Into Structure'],
  },
  {
    slug: 'criminal-trespass-enter-structure',
    displayName: 'Criminal Trespass — Enter Structure',
    statuteCode: '18 § 3503(a)(1)(i)',
    aliases: ['Crim Tres-Enter Structure'],
  },
  {
    slug: 'defiant-trespass-actual-communication',
    displayName: 'Defiant Trespasser — Actual Communication',
    statuteCode: '18 § 3503(b)(1)(i)',
    aliases: ['Def Tres Actual Communication To'],
  },
  {
    slug: 'defiant-trespass-posted',
    displayName: 'Defiant Trespasser — Posted',
    statuteCode: '18 § 3503(b)(1)(ii)',
    aliases: ['Def Tres Posted'],
  },

  // --- Theft / property fraud ------------------------------------------------
  {
    slug: 'receiving-stolen-property',
    displayName: 'Receiving Stolen Property',
    statuteCode: '18 § 3925(a)',
    aliases: ['Receiving Stolen Property'],
  },
  {
    slug: 'theft-unlawful-taking-movable',
    displayName: 'Theft by Unlawful Taking — Movable Property',
    statuteCode: '18 § 3921(a)',
    aliases: ['Theft By Unlaw Taking-Movable Prop'],
  },
  // Retail theft ("Retail Theft-Take Mdse", 18 § 3929 / (a)(1)) is owned by the
  // Sprint 2 demo `retail-theft` row: the roster additively attaches its CPCMS
  // description to that demo row via DEMO_ALIAS_ADDITIONS (Decision 4) rather
  // than defining a competing real entry.
  {
    slug: 'unauthorized-use-motor-vehicle',
    displayName: 'Unauthorized Use of Motor or Other Vehicles',
    statuteCode: '18 § 3928(a)',
    aliases: ['Unauth Use Motor/Other Vehicles'],
  },
  {
    slug: 'theft-by-deception',
    displayName: 'Theft by Deception — False Impression',
    statuteCode: '18 § 3922(a)(1)',
    aliases: ['Theft By Decep-False Impression'],
  },
  {
    slug: 'identity-theft',
    displayName: 'Identity Theft',
    statuteCode: '18 § 4120(a)',
    aliases: ['Identity Theft'],
  },
  {
    slug: 'access-device-fraud',
    displayName: 'Access Device Fraud',
    statuteCode: '18 § 4106(a)(1)',
    aliases: ['Access Device Used To Obt Or Att Obt Prop/Service'],
  },
  {
    slug: 'insurance-fraud',
    displayName: 'Insurance Fraud',
    statuteCode: '18 § 4117',
    aliases: ['False/Fraud/Incomp Insurance Claim', 'Fraud Document - Insurance Rate Determ'],
  },

  // --- Inchoate offenses (statute-only: compound/heterogeneous offense text) --
  {
    slug: 'criminal-conspiracy',
    displayName: 'Criminal Conspiracy',
    statuteCode: '18 § 903',
    aliases: [],
  },
  {
    slug: 'criminal-conspiracy-903c',
    displayName: 'Criminal Conspiracy (§ 903(c))',
    statuteCode: '18 § 903(c)',
    aliases: [],
  },
  {
    slug: 'criminal-attempt',
    displayName: 'Criminal Attempt',
    statuteCode: '18 § 901(a)',
    aliases: [],
  },
  {
    slug: 'criminal-attempt-901',
    displayName: 'Criminal Attempt (Generally)',
    statuteCode: '18 § 901',
    aliases: [],
  },

  // --- Public order / administration of justice ------------------------------
  {
    slug: 'endangering-welfare-children',
    displayName: 'Endangering Welfare of Children',
    statuteCode: '18 § 4304(a)(1)',
    aliases: ['Endangering Welfare of Children - Parent/Guardian/Other Commits Offense'],
  },
  {
    slug: 'criminal-mischief-damage-property',
    displayName: 'Criminal Mischief — Damage to Property',
    statuteCode: '18 § 3304(a)(5)',
    aliases: ['Criminal Mischief - Damage Property'],
  },
  {
    slug: 'tamper-public-records',
    displayName: 'Tampering With Public Records or Information',
    statuteCode: '18 § 4911',
    aliases: ['Tamper With Public Record/information'],
  },
  {
    slug: 'resisting-arrest',
    displayName: 'Resisting Arrest or Other Law Enforcement',
    statuteCode: '18 § 5104',
    aliases: ['Resist Arrest/Other Law Enforce'],
  },
  {
    slug: 'evading-arrest-on-foot',
    displayName: 'Evading Arrest or Detention on Foot',
    statuteCode: '18 § 5104.2(a)',
    aliases: ['Evading Arrest or Detention on Foot'],
  },
  {
    slug: 'disorderly-conduct-hazardous',
    displayName: 'Disorderly Conduct — Hazardous or Physically Offensive Condition',
    statuteCode: '18 § 5503(a)(4)',
    aliases: ['Disorderly Conduct Hazardous/Physi Off'],
  },
  {
    slug: 'disorderly-conduct-fighting',
    displayName: 'Disorderly Conduct — Engage in Fighting',
    statuteCode: '18 § 5503(a)(1)',
    aliases: ['Disorderly Conduct Engage In Fighting'],
  },
  {
    slug: 'criminal-use-communication-facility',
    displayName: 'Criminal Use of Communication Facility',
    statuteCode: '18 § 7512(a)',
    aliases: ['Criminal Use Of Communication Facility'],
  },
  {
    slug: 'fleeing-eluding-officer',
    displayName: 'Fleeing or Attempting to Elude Police Officer',
    statuteCode: '75 § 3733(a)',
    aliases: ['Fleeing or Attempting to Elude Officer'],
  },
  {
    slug: 'contempt-pfa-order',
    displayName: 'Contempt for Violation of Order or Agreement (PFA)',
    statuteCode: '23 § 6114(a)',
    aliases: ['Contempt For Violation of Order or Agreement'],
  },
  {
    slug: 'medical-assistance-fraud',
    displayName: 'Medical Assistance Provider Prohibited Acts',
    statuteCode: '62 § 1407(a)(1)',
    aliases: [
      'False/Fraud Med Assist Claim',
      "Submit Claim Serv Not Rend'd To Pt",
      'Submit Claim W/False Info',
      "Submit Claim Serv Not Rend'd By Prov",
    ],
  },

  // --- Harassment (subsections; demo owns bare 18 § 2709) --------------------
  {
    slug: 'harassment-physical-contact',
    displayName: 'Harassment — Subject Other to Physical Contact',
    statuteCode: '18 § 2709(a)(1)',
    aliases: ['Harassment - Subject Other to Physical Contact'],
  },
  {
    slug: 'harassment-communications',
    displayName: 'Harassment — Lewd or Threatening Communications',
    statuteCode: '18 § 2709(a)(4)',
    aliases: ['Harassment - Comm. Lewd, Threatening, Etc. Language'],
  },

  // --- Sexual offenses -------------------------------------------------------
  {
    slug: 'corruption-of-minors',
    displayName: 'Corruption of Minors',
    statuteCode: '18 § 6301(a)(1)(i)',
    aliases: ['Corruption Of Minors'],
  },
  {
    slug: 'corruption-of-minors-adult',
    displayName: 'Corruption of Minors — Defendant Age 18 or Above',
    statuteCode: '18 § 6301(a)(1)(ii)',
    aliases: ['Corruption Of Minors - Defendant Age 18 or Above'],
  },
  {
    slug: 'indecent-assault-under-13',
    displayName: 'Indecent Assault — Person Less Than 13 Years of Age',
    statuteCode: '18 § 3126(a)(7)',
    aliases: ['Indecent Assault Person Less than 13 Years of Age'],
  },
  {
    slug: 'indecent-assault-without-consent',
    displayName: 'Indecent Assault — Without Consent of Other',
    statuteCode: '18 § 3126(a)(1)',
    aliases: ['Indec Asslt-W/O Cons Of Other'],
  },
  {
    slug: 'indecent-assault-under-16',
    displayName: 'Indecent Assault — Person Less Than 16 Years of Age',
    statuteCode: '18 § 3126(a)(8)',
    aliases: ['Ind Asslt Person Less 16 Yrs Age'],
  },
  {
    slug: 'rape-of-child',
    displayName: 'Rape of a Child',
    statuteCode: '18 § 3121(c)',
    aliases: ['Rape of Child'],
  },
  {
    slug: 'sexual-assault',
    displayName: 'Sexual Assault',
    statuteCode: '18 § 3124.1',
    aliases: ['Sexual Assault'],
  },
];
