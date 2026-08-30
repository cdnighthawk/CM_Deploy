import { Stack, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from 'react-native';

import { ApiError } from '@/src/api/client';
import {
  getOrCreateDailyPretask,
  saveDailyPretask,
  submitDailyPretask,
  type DailyPretask,
  type PretaskChecklist,
  type PretaskTask,
} from '@/src/api/safety';

const CHECKLIST: { key: keyof PretaskChecklist; label: string }[] = [
  { key: 'supervisor_walkthrough', label: 'Supervisor walk-through of the work area' },
  { key: 'coordination_other_crafts', label: 'Coordination with other crafts' },
  { key: 'equipment_check', label: 'Tools, materials, and equipment are safe' },
  { key: 'training_complete', label: 'Required training is complete' },
  { key: 'sufficient_personnel', label: 'Sufficient personnel for the task' },
];

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function emptyTask(): PretaskTask {
  return { jha_complete: false, task: '', hazards: '', steps: '' };
}

export default function DailyPretaskScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [item, setItem] = useState<DailyPretask | null>(null);

  const locked = item?.status === 'submitted';

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const row = await getOrCreateDailyPretask(id, todayIso());
      setItem(row);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Failed to load daily pretask');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  function patch(partial: Partial<DailyPretask>) {
    setItem((prev) => (prev ? { ...prev, ...partial } : prev));
  }

  async function onSave() {
    if (!item) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const saved = await saveDailyPretask(item.id, {
        company_name: item.company_name,
        area_of_work: item.area_of_work,
        checklist: item.checklist,
        tasks: item.tasks,
        near_miss: item.near_miss,
        near_miss_notes: item.near_miss_notes,
        required_permits: item.required_permits,
        items_concerns: item.items_concerns,
        quality_previous_day: item.quality_previous_day,
        present_items_concerns: item.present_items_concerns,
        attendees: item.attendees,
        supervisor_name: item.supervisor_name,
        supervisor_signature: item.supervisor_signature,
      });
      setItem(saved);
      setNotice('Saved draft.');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  }

  async function onSubmit() {
    if (!item) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const saved = await saveDailyPretask(item.id, {
        company_name: item.company_name,
        area_of_work: item.area_of_work,
        checklist: item.checklist,
        tasks: item.tasks,
        near_miss: item.near_miss,
        near_miss_notes: item.near_miss_notes,
        required_permits: item.required_permits,
        items_concerns: item.items_concerns,
        quality_previous_day: item.quality_previous_day,
        present_items_concerns: item.present_items_concerns,
        attendees: item.attendees,
        supervisor_name: item.supervisor_name,
        supervisor_signature: item.supervisor_signature,
      });
      const submitted = await submitDailyPretask(saved.id);
      setItem(submitted);
      setNotice('Submitted. This plan is locked.');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Submit failed');
    } finally {
      setSaving(false);
    }
  }

  function setTask(index: number, next: Partial<PretaskTask>) {
    if (!item) return;
    const tasks = item.tasks.map((row, i) => (i === index ? { ...row, ...next } : row));
    patch({ tasks });
  }

  if (loading) {
    return (
      <View style={styles.root}>
        <Stack.Screen options={{ title: 'Daily pretask' }} />
        <ActivityIndicator style={{ marginTop: 24 }} />
      </View>
    );
  }

  if (!item) {
    return (
      <View style={styles.root}>
        <Stack.Screen options={{ title: 'Daily pretask' }} />
        <Text style={styles.error}>{error || 'No pretask'}</Text>
        <Pressable style={styles.btn} onPress={load}>
          <Text style={styles.btnText}>Retry</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.content}>
      <Stack.Screen options={{ title: 'Daily pretask' }} />
      <Text style={styles.kicker}>
        {item.project_number ? `${item.project_number} — ` : ''}
        {item.project_name} · {item.work_date}
      </Text>
      <Text style={styles.status}>{item.status === 'submitted' ? 'Submitted' : 'Draft'}</Text>
      {error ? <Text style={styles.error}>{error}</Text> : null}
      {notice ? <Text style={styles.notice}>{notice}</Text> : null}

      <Text style={styles.label}>Area of work</Text>
      <TextInput
        style={styles.input}
        value={item.area_of_work}
        onChangeText={(area_of_work) => patch({ area_of_work })}
        editable={!locked && !saving}
        placeholder="e.g. basement/kitchen"
      />

      <Text style={styles.section}>Prior to the start of a task</Text>
      {CHECKLIST.map((row) => (
        <View key={row.key} style={styles.checkRow}>
          <Switch
            value={!!item.checklist[row.key]}
            disabled={locked || saving}
            onValueChange={(v) => patch({ checklist: { ...item.checklist, [row.key]: v } })}
          />
          <Text style={styles.checkLabel}>{row.label}</Text>
        </View>
      ))}

      <Text style={styles.section}>Task analysis</Text>
      {item.tasks.map((task, index) => (
        <View key={index} style={styles.taskCard}>
          <View style={styles.checkRow}>
            <Switch
              value={task.jha_complete}
              disabled={locked || saving}
              onValueChange={(v) => setTask(index, { jha_complete: v })}
            />
            <Text style={styles.checkLabel}>JHA complete</Text>
          </View>
          <TextInput
            style={styles.input}
            placeholder="Task"
            value={task.task}
            editable={!locked && !saving}
            onChangeText={(taskText) => setTask(index, { task: taskText })}
          />
          <TextInput
            style={[styles.input, styles.multiline]}
            placeholder="Hazards"
            value={task.hazards}
            multiline
            editable={!locked && !saving}
            onChangeText={(hazards) => setTask(index, { hazards })}
          />
          <TextInput
            style={[styles.input, styles.multiline]}
            placeholder="Steps to do it safely / tools"
            value={task.steps}
            multiline
            editable={!locked && !saving}
            onChangeText={(steps) => setTask(index, { steps })}
          />
        </View>
      ))}
      {!locked ? (
        <Pressable style={styles.secondary} onPress={() => patch({ tasks: [...item.tasks, emptyTask()] })}>
          <Text style={styles.secondaryText}>Add task</Text>
        </Pressable>
      ) : null}

      <Text style={styles.label}>Supervisor printed name</Text>
      <TextInput
        style={styles.input}
        value={item.supervisor_name}
        onChangeText={(supervisor_name) => patch({ supervisor_name })}
        editable={!locked && !saving}
      />
      <Text style={styles.label}>Supervisor signature (type name for now)</Text>
      <TextInput
        style={styles.input}
        value={item.supervisor_signature}
        onChangeText={(supervisor_signature) => patch({ supervisor_signature })}
        editable={!locked && !saving}
      />

      {!locked ? (
        <View style={styles.actions}>
          <Pressable style={styles.btn} onPress={onSave} disabled={saving}>
            <Text style={styles.btnText}>{saving ? 'Working…' : 'Save draft'}</Text>
          </Pressable>
          <Pressable style={[styles.btn, styles.btnPrimary]} onPress={onSubmit} disabled={saving}>
            <Text style={[styles.btnText, styles.btnPrimaryText]}>Submit plan</Text>
          </Pressable>
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#f8fafc' },
  content: { padding: 16, paddingBottom: 40 },
  kicker: { fontSize: 14, color: '#475569', marginBottom: 4 },
  status: { fontSize: 13, fontWeight: '600', color: '#1F4E5F', marginBottom: 12 },
  section: { fontSize: 16, fontWeight: '700', color: '#0f172a', marginTop: 16, marginBottom: 8 },
  label: { fontSize: 13, fontWeight: '600', color: '#334155', marginTop: 10, marginBottom: 4 },
  input: {
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#e2e8f0',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 15,
    color: '#0f172a',
    marginBottom: 8,
  },
  multiline: { minHeight: 64, textAlignVertical: 'top' },
  checkRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 },
  checkLabel: { flex: 1, fontSize: 14, color: '#1e293b' },
  taskCard: {
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#e2e8f0',
    borderRadius: 10,
    padding: 12,
    marginBottom: 10,
  },
  actions: { marginTop: 16, gap: 10 },
  btn: {
    borderWidth: 1,
    borderColor: '#1F4E5F',
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: 'center',
    backgroundColor: '#fff',
  },
  btnPrimary: { backgroundColor: '#1F4E5F' },
  btnText: { color: '#1F4E5F', fontWeight: '700' },
  btnPrimaryText: { color: '#fff' },
  secondary: { paddingVertical: 10, alignItems: 'center' },
  secondaryText: { color: '#1e40af', fontWeight: '600' },
  error: { color: '#b91c1c', marginBottom: 8 },
  notice: { color: '#166534', marginBottom: 8 },
});
