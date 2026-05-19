import { apiFetch } from '@/src/api/client';

export type ProjectSummary = {
  id: string;
  number: string | null;
  name: string;
  city: string | null;
  state: string | null;
  status: string | null;
  project_type: string | null;
  updated_at: string | null;
};

type ProjectsListResponse = {
  items: ProjectSummary[];
  total: number;
  entity: string;
  project_scope?: 'all' | 'assigned';
};

type ProjectDetailResponse = {
  item: ProjectSummary & Record<string, unknown>;
  entity: string;
};

export async function fetchProjects(): Promise<ProjectSummary[]> {
  const data = await apiFetch<ProjectsListResponse>('/api/v1/projects?limit=500');
  return data.items ?? [];
}

export async function fetchProject(projectId: string): Promise<ProjectDetailResponse['item']> {
  try {
    const data = await apiFetch<ProjectDetailResponse>(`/api/v1/projects/${projectId}`);
    return data.item;
  } catch (err) {
    const status = (err as { status?: number }).status;
    if (status === 404) {
      throw new Error('Project not found or you are not assigned to this job.');
    }
    throw err;
  }
}
