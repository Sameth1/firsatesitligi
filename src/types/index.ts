export type Category = {
  id: string
  slug: string
  label_tr: string
  label_en: string
  color: string
}

export type Document = {
  name: string
  is_required: boolean
  notes: string | null
}

export type Opportunity = {
  id: string
  title: string
  official_url: string
  deadline: string | null
  deadline_notes: string | null
  host_countries: string[]
  funding_type: string
  funding_notes: string | null
  eligibility_notes: string | null
  language_requirement: string | null
  age_min: number | null
  age_max: number | null
  category_slug: string
  category_label_tr: string
  category_color: string
  documents: Document[]
  is_featured: boolean
  days_until_deadline: number | null
}

export type MatchParams = {
  p_host_country?: string | null
  p_category_slug?: string | null
  p_citizenship?: string
  p_age?: number | null
  p_study_level?: string | null
  p_highest_edu?: string | null
  p_field?: string | null
  p_language?: string | null
}

export type FilterOptions = {
  fields: string[]
  languages: string[]
}
