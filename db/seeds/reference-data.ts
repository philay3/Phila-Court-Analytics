/**
 * Reference seed data for the ref.* layer.
 *
 * Charges are real Pennsylvania statutes — statutes are not people. Judges
 * are OBVIOUSLY FAKE by standing decision: fabricated statistics must never
 * be attachable to a real Philadelphia judge. Never replace these with
 * real-sounding names.
 *
 * Grades are intentionally absent: grading varies by offense circumstances,
 * so seeds must not invent one.
 */

export interface ChargeSeed {
  slug: string;
  displayName: string;
  statuteCode: string;
  aliases: readonly string[];
}

export interface JudgeSeed {
  slug: string;
  displayName: string;
  aliases: readonly string[];
}

export const CHARGE_SEEDS: readonly ChargeSeed[] = [
  {
    slug: 'retail-theft',
    displayName: 'Retail Theft',
    statuteCode: '18 § 3929',
    aliases: ['shoplifting'],
  },
  {
    slug: 'simple-assault',
    displayName: 'Simple Assault',
    statuteCode: '18 § 2701',
    aliases: ['assault (simple)'],
  },
  {
    slug: 'dui-general-impairment',
    displayName: 'DUI: General Impairment',
    statuteCode: '75 § 3802(a)(1)',
    aliases: ['driving under the influence', 'drunk driving'],
  },
  {
    slug: 'possession-controlled-substance',
    displayName: 'Possession of a Controlled Substance',
    statuteCode: '35 § 780-113(a)(16)',
    aliases: ['drug possession'],
  },
  {
    slug: 'criminal-trespass',
    displayName: 'Criminal Trespass',
    statuteCode: '18 § 3503',
    aliases: ['trespassing'],
  },
  {
    // Charge-unavailable fixture (task 13.2a): a real, active charge that
    // deliberately appears in NO aggregate distribution. Requesting it returns
    // the HTTP 200 charge-only unavailable arm (published run exists, zero rows
    // for this charge). Do not add aggregate rows for it.
    slug: 'harassment',
    displayName: 'Harassment',
    statuteCode: '18 § 2709',
    aliases: ['harassing communications'],
  },
];

export const JUDGE_SEEDS: readonly JudgeSeed[] = [
  {
    slug: 'judge-testina-placeholder',
    displayName: 'Judge Testina Placeholder',
    aliases: ['T. Placeholder'],
  },
  {
    slug: 'judge-samuel-seeddata',
    displayName: 'Judge Samuel Seeddata',
    aliases: ['S. Seeddata'],
  },
  {
    slug: 'judge-fakename-example',
    displayName: 'Judge Fakename Example',
    aliases: ['F. Example'],
  },
];
