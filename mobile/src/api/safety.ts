import { apiFetch } from '@/src/api/client';

export type PretaskChecklist = {
  supervisor_walkthrough: boolean;
  coordination_other_crafts: boolean;
  equipment_check: boolean;
  training_complete: boolean;
  sufficient_personnel: boolean;
};

export type PretaskTask = {
  jha_complete: boolean;
  task: string;
  hazards: string;
  steps: string;
};

export type PretaskAttendee = {
  print_name: string;
  signature: string;
};

export type DailyPretask = {
  id: string;
  project_id: string;
  project_name: string;
  project_number: string | null;
  work_date: string;
  crew_lead_user_id: string;
  crew_lead_name: string;
  daily_report_id: string | null;
  client_id: string | null;
  company_name: string;
  area_of_work: string;
  status: 'draft' | 'submitted';
  checklist: PretaskChecklist;
  tasks: PretaskTask[];
  near_miss: boolean;
  near_miss_notes: string;
  required_permits: string;
  items_concerns: string;
  quality_previous_day: string;
  present_items_concerns: string;
  attendees: PretaskAttendee[];
  supervisor_name: string;
  supervisor_signature: string;
  submitted_at: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type DailyPretaskListItem = {
  id: string;
  project_id: string;
  project_name: string;
  project_number: string | null;
  work_date: string;
  area_of_work: string;
  status: 'draft' | 'submitted';
  crew_lead_name: string;
  task_count: number;
  attendee_count: number;
  near_miss: boolean;
  submitted_at: string | null;
  updated_at: string | null;
};

type PretaskResponse = { item: DailyPretask; entity: string; created?: boolean };
type PretaskListResponse = { items: DailyPretaskListItem[]; total: number; entity: string };

export type PretaskWrite = Partial<
  Pick<
    DailyPretask,
    | 'company_name'
    | 'area_of_work'
    | 'checklist'
    | 'tasks'
    | 'near_miss'
    | 'near_miss_notes'
    | 'required_permits'
    | 'items_concerns'
    | 'quality_previous_day'
    | 'present_items_concerns'
    | 'attendees'
    | 'supervisor_name'
    | 'supervisor_signature'
    | 'daily_report_id'
    | 'client_id'
  >
> & { work_date?: string; status?: 'draft' | 'submitted' };

export async function getOrCreateDailyPretask(
  projectId: string,
  workDate: string,
  clientId?: string,
): Promise<DailyPretask> {
  const qs = new URLSearchParams({ date: workDate });
  if (clientId) qs.set('client_id', clientId);
  const data = await apiFetch<PretaskResponse>(
    `/api/v1/projects/${projectId}/daily-pretasks?${qs.toString()}`,
  );
  return data.item;
}

export async function saveDailyPretask(id: string, body: PretaskWrite): Promise<DailyPretask> {
  const data = await apiFetch<PretaskResponse>(`/api/v1/daily-pretasks/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return data.item;
}

export async function submitDailyPretask(id: string, body: PretaskWrite = {}): Promise<DailyPretask> {
  const data = await apiFetch<PretaskResponse>(`/api/v1/daily-pretasks/${id}/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return data.item;
}

export async function listDailyPretasks(params?: {
  projectId?: string;
  date?: string;
}): Promise<DailyPretaskListItem[]> {
  const qs = new URLSearchParams();
  if (params?.projectId) qs.set('project_id', params.projectId);
  if (params?.date) qs.set('date', params.date);
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  const data = await apiFetch<PretaskListResponse>(`/api/v1/safety/pretasks${suffix}`);
  return data.items ?? [];
}
