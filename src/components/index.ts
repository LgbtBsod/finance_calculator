/**
 * OpenUI5-inspired Components built with vanilla TypeScript
 * Following SRP: Each component has one responsibility
 * UX Improvements: Switches instead of checkboxes, inline editing, grouped expenses
 */

import { IExpenseGroup, IExpenseItem, IDebt, IVacation, ISalarySettings } from '../types';
import { formatCurrency, formatDate, generateId } from '../utils/helpers';

// ═══════════════════════════════════════════════════════════════
// SWITCH COMPONENT (replaces all checkboxes)
// ═══════════════════════════════════════════════════════════════

export interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
  disabled?: boolean;
  id?: string;
}

export function createSwitch(props: SwitchProps): HTMLElement {
  const container = document.createElement('label');
  container.className = 'switch-container';
  if (props.id) container.htmlFor = props.id;
  
  const input = document.createElement('input');
  input.type = 'checkbox';
  input.checked = props.checked;
  input.disabled = !!props.disabled;
  input.addEventListener('change', (e) => {
    props.onChange((e.target as HTMLInputElement).checked);
  });
  
  const slider = document.createElement('span');
  slider.className = 'slider';
  
  container.appendChild(input);
  container.appendChild(slider);
  
  if (props.label) {
    const labelSpan = document.createElement('span');
    labelSpan.className = 'switch-label';
    labelSpan.textContent = props.label;
    container.appendChild(labelSpan);
  }
  
  return container;
}

// ═══════════════════════════════════════════════════════════════
// COLOR PICKER COMPONENT (for expense group grouping)
// ═══════════════════════════════════════════════════════════════

const COLORS = [
  { name: 'red', value: '#ef4444' },
  { name: 'orange', value: '#f97316' },
  { name: 'amber', value: '#eab308' },
  { name: 'green', value: '#22c55e' },
  { name: 'blue', value: '#3b82f6' },
  { name: 'violet', value: '#8b5cf6' },
  { name: 'pink', value: '#ec4899' },
  { name: 'teal', value: '#14b8a6' },
];

export interface ColorPickerProps {
  selectedColor: string;
  onSelectColor: (color: string) => void;
}

export function createColorPicker(props: ColorPickerProps): HTMLElement {
  const container = document.createElement('div');
  container.className = 'color-picker';
  
  COLORS.forEach((color) => {
    const option = document.createElement('button');
    option.className = `color-option ${color.name}`;
    option.style.backgroundColor = color.value;
    if (props.selectedColor === color.value) {
      option.classList.add('selected');
    }
    option.addEventListener('click', () => {
      props.onSelectColor(color.value);
      // Update selected state
      Array.from(container.children).forEach(child => {
        child.classList.remove('selected');
      });
      option.classList.add('selected');
    });
    container.appendChild(option);
  });
  
  return container;
}

// ═══════════════════════════════════════════════════════════════
// EXPENSE GROUP CARD (with color grouping)
// ═══════════════════════════════════════════════════════════════

export interface ExpenseGroupCardProps {
  group: IExpenseGroup;
  onEdit: (group: IExpenseGroup) => void;
  onDelete: (id: string) => void;
}

export function createExpenseGroupCard(props: ExpenseGroupCardProps): HTMLElement {
  const card = document.createElement('div');
  card.className = 'expense-group-card';
  card.style.borderLeftColor = props.group.color;
  
  const header = document.createElement('div');
  header.className = 'card-header';
  
  const colorIndicator = document.createElement('span');
  colorIndicator.className = 'color-indicator';
  colorIndicator.style.backgroundColor = props.group.color;
  
  const title = document.createElement('h4');
  title.textContent = props.group.name;
  
  const actions = document.createElement('div');
  actions.className = 'card-actions';
  
  const editBtn = document.createElement('button');
  editBtn.className = 'btn btn-sm btn-secondary';
  editBtn.textContent = '✏️';
  editBtn.addEventListener('click', () => props.onEdit(props.group));
  
  const deleteBtn = document.createElement('button');
  deleteBtn.className = 'btn btn-sm btn-danger';
  deleteBtn.textContent = '🗑️';
  deleteBtn.addEventListener('click', () => props.onDelete(props.group.id));
  
  actions.appendChild(editBtn);
  actions.appendChild(deleteBtn);
  header.appendChild(colorIndicator);
  header.appendChild(title);
  header.appendChild(actions);
  card.appendChild(header);
  
  return card;
}

// ═══════════════════════════════════════════════════════════════
// EDITABLE TABLE ROW (inline editing instead of separate form)
// ═══════════════════════════════════════════════════════════════

export interface EditableRowProps<T> {
  item: T;
  columns: Array<{
    key: keyof T;
    label: string;
    render?: (value: any, item: T) => string;
    editor?: (value: any, onChange: (val: any) => void) => HTMLElement;
  }>;
  onSave: (updates: Partial<T>) => void;
  onDelete: () => void;
  isEditing: boolean;
  onEditToggle: () => void;
}

export function createEditableRow<T extends { id: string }>(
  props: EditableRowProps<T>
): HTMLElement {
  const row = document.createElement('tr');
  row.className = props.isEditing ? 'editing' : '';
  
  props.columns.forEach((col) => {
    const cell = document.createElement('td');
    
    if (props.isEditing && col.editor) {
      const value = props.item[col.key];
      const editor = col.editor(value, (newVal) => {
        props.onSave({ [col.key]: newVal } as Partial<T>);
      });
      cell.appendChild(editor);
    } else {
      const renderValue = col.render 
        ? col.render(props.item[col.key], props.item)
        : String(props.item[col.key] ?? '');
      cell.textContent = renderValue;
    }
    
    row.appendChild(cell);
  });
  
  // Actions column
  const actionsCell = document.createElement('td');
  actionsCell.className = 'actions-cell';
  
  if (props.isEditing) {
    const saveBtn = document.createElement('button');
    saveBtn.className = 'btn btn-sm btn-primary';
    saveBtn.textContent = '💾';
    saveBtn.addEventListener('click', props.onEditToggle);
    actionsCell.appendChild(saveBtn);
  } else {
    const editBtn = document.createElement('button');
    editBtn.className = 'btn btn-sm btn-secondary';
    editBtn.textContent = '✏️';
    editBtn.addEventListener('click', props.onEditToggle);
    
    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'btn btn-sm btn-danger';
    deleteBtn.textContent = '🗑️';
    deleteBtn.addEventListener('click', props.onDelete);
    
    actionsCell.appendChild(editBtn);
    actionsCell.appendChild(deleteBtn);
  }
  
  row.appendChild(actionsCell);
  
  return row;
}

// ═══════════════════════════════════════════════════════════════
// DEBT CARD WITH REPAYMENTS (multiple repayments support)
// ═══════════════════════════════════════════════════════════════

export interface DebtCardProps {
  debt: IDebt;
  onAddRepayment: (debtId: string, amount: number, date: string, note?: string) => void;
  onDeleteRepayment: (debtId: string, repaymentId: string) => void;
  onDeleteDebt: (id: string) => void;
}

export function createDebtCard(props: DebtCardProps): HTMLElement {
  const card = document.createElement('div');
  card.className = 'debt-card';
  
  const remaining = props.debt.totalAmount - 
    props.debt.repayments.reduce((sum, r) => sum + r.amount, 0);
  
  // Header
  const header = document.createElement('div');
  header.className = 'debt-header';
  
  const title = document.createElement('h4');
  title.textContent = props.debt.title;
  
  const total = document.createElement('span');
  total.className = 'debt-total';
  total.textContent = formatCurrency(props.debt.totalAmount);
  
  const deleteBtn = document.createElement('button');
  deleteBtn.className = 'btn btn-sm btn-danger';
  deleteBtn.textContent = '🗑️';
  deleteBtn.addEventListener('click', () => props.onDeleteDebt(props.debt.id));
  
  header.appendChild(title);
  header.appendChild(total);
  header.appendChild(deleteBtn);
  card.appendChild(header);
  
  // Progress bar
  const progress = (props.debt.totalAmount - remaining) / props.debt.totalAmount * 100;
  const progressBar = document.createElement('div');
  progressBar.className = 'progress-bar';
  const progressFill = document.createElement('div');
  progressFill.className = 'progress-fill';
  progressFill.style.width = `${progress}%`;
  progressBar.appendChild(progressFill);
  card.appendChild(progressBar);
  
  // Remaining info
  const remainingInfo = document.createElement('div');
  remainingInfo.className = 'debt-remaining';
  remainingInfo.innerHTML = `Осталось: <strong>${formatCurrency(remaining)}</strong>`;
  card.appendChild(remainingInfo);
  
  // Repayments list
  const repaymentsSection = document.createElement('div');
  repaymentsSection.className = 'repayments-section';
  
  const repaymentsTitle = document.createElement('h5');
  repaymentsTitle.textContent = 'Возвраты:';
  repaymentsSection.appendChild(repaymentsTitle);
  
  if (props.debt.repayments.length > 0) {
    const list = document.createElement('ul');
    list.className = 'repayments-list';
    
    props.debt.repayments.forEach((repayment) => {
      const li = document.createElement('li');
      li.className = 'repayment-item';
      
      const dateSpan = document.createElement('span');
      dateSpan.className = 'repayment-date';
      dateSpan.textContent = formatDate(repayment.date);
      
      const amountSpan = document.createElement('span');
      amountSpan.className = 'repayment-amount';
      amountSpan.textContent = formatCurrency(repayment.amount);
      
      const deleteRepBtn = document.createElement('button');
      deleteRepBtn.className = 'btn btn-xs btn-danger';
      deleteRepBtn.textContent = '×';
      deleteRepBtn.addEventListener('click', () => {
        props.onDeleteRepayment(props.debt.id, repayment.id);
      });
      
      li.appendChild(dateSpan);
      li.appendChild(amountSpan);
      li.appendChild(deleteRepBtn);
      list.appendChild(li);
    });
    
    repaymentsSection.appendChild(list);
  }
  
  // Add repayment form
  const addForm = document.createElement('div');
  addForm.className = 'add-repayment-form';
  
  const amountInput = document.createElement('input');
  amountInput.type = 'number';
  amountInput.className = 'input input-sm';
  amountInput.placeholder = 'Сумма';
  amountInput.min = '0';
  
  const dateInput = document.createElement('input');
  dateInput.type = 'date';
  dateInput.className = 'input input-sm';
  dateInput.valueAsDate = new Date();
  
  const noteInput = document.createElement('input');
  noteInput.type = 'text';
  noteInput.className = 'input input-sm';
  noteInput.placeholder = 'Комментарий';
  
  const addBtn = document.createElement('button');
  addBtn.className = 'btn btn-sm btn-primary';
  addBtn.textContent = '+ Добавить возврат';
  addBtn.addEventListener('click', () => {
    const amount = parseFloat(amountInput.value);
    const date = dateInput.value;
    const note = noteInput.value || undefined;
    
    if (amount > 0 && date) {
      props.onAddRepayment(props.debt.id, amount, date, note);
      amountInput.value = '';
      noteInput.value = '';
    }
  });
  
  addForm.appendChild(amountInput);
  addForm.appendChild(dateInput);
  addForm.appendChild(noteInput);
  addForm.appendChild(addBtn);
  repaymentsSection.appendChild(addForm);
  
  card.appendChild(repaymentsSection);
  
  return card;
}

// ═══════════════════════════════════════════════════════════════
// INCOME SECTION (top right placement)
// ═══════════════════════════════════════════════════════════════

export interface IncomeSectionProps {
  vacations: IVacation[];
  onAddVacation: (amount: number, date: string) => void;
  onDeleteVacation: (id: string) => void;
}

export function createIncomeSection(props: IncomeSectionProps): HTMLElement {
  const section = document.createElement('div');
  section.className = 'income-section';
  
  const title = document.createElement('h3');
  title.textContent = '💰 Начисления (Отпускные)';
  section.appendChild(title);
  
  // Add form
  const form = document.createElement('div');
  form.className = 'income-form';
  
  const amountInput = document.createElement('input');
  amountInput.type = 'number';
  amountInput.className = 'input';
  amountInput.placeholder = 'Сумма отпускных';
  amountInput.min = '0';
  
  const dateInput = document.createElement('input');
  dateInput.type = 'date';
  dateInput.className = 'input';
  dateInput.valueAsDate = new Date();
  
  const addBtn = document.createElement('button');
  addBtn.className = 'btn btn-primary';
  addBtn.textContent = '+ Добавить';
  addBtn.addEventListener('click', () => {
    const amount = parseFloat(amountInput.value);
    const date = dateInput.value;
    
    if (amount > 0 && date) {
      props.onAddVacation(amount, date);
      amountInput.value = '';
    }
  });
  
  form.appendChild(amountInput);
  form.appendChild(dateInput);
  form.appendChild(addBtn);
  section.appendChild(form);
  
  // Vacations list
  if (props.vacations.length > 0) {
    const list = document.createElement('div');
    list.className = 'vacations-list';
    
    props.vacations.forEach((vacation) => {
      const item = document.createElement('div');
      item.className = 'vacation-item';
      
      const dateSpan = document.createElement('span');
      dateSpan.textContent = formatDate(vacation.payoutDate);
      
      const amountSpan = document.createElement('span');
      amountSpan.className = 'vacation-amount';
      amountSpan.textContent = formatCurrency(vacation.totalAmount);
      
      const deleteBtn = document.createElement('button');
      deleteBtn.className = 'btn btn-sm btn-danger';
      deleteBtn.textContent = '🗑️';
      deleteBtn.addEventListener('click', () => props.onDeleteVacation(vacation.id));
      
      item.appendChild(dateSpan);
      item.appendChild(amountSpan);
      item.appendChild(deleteBtn);
      list.appendChild(item);
    });
    
    section.appendChild(list);
  }
  
  return section;
}

// ═══════════════════════════════════════════════════════════════
// SETTINGS PANEL (with inclusive date switch)
// ═══════════════════════════════════════════════════════════════

export interface SettingsPanelProps {
  settings: ISalarySettings;
  onUpdate: (updates: Partial<ISalarySettings>) => void;
}

export function createSettingsPanel(props: SettingsPanelProps): HTMLElement {
  const panel = document.createElement('div');
  panel.className = 'settings-panel';
  
  // Base Salary
  const salaryGroup = createInputGroup(
    'Оклад (₽)',
    'number',
    props.settings.baseSalary,
    (val) => props.onUpdate({ baseSalary: parseFloat(val) })
  );
  panel.appendChild(salaryGroup);
  
  // Tax Rate
  const taxGroup = createInputGroup(
    'НДФЛ (%)',
    'number',
    props.settings.taxRate,
    (val) => props.onUpdate({ taxRate: parseFloat(val) }),
    { min: 0, max: 99, step: 0.5 }
  );
  panel.appendChild(taxGroup);
  
  // KEF
  const kefGroup = createInputGroup(
    'КЭФ',
    'number',
    props.settings.kef,
    (val) => props.onUpdate({ kef: parseFloat(val) }),
    { min: 0, step: 0.01 }
  );
  panel.appendChild(kefGroup);
  
  // Advance Cutoff Day
  const cutoffGroup = createInputGroup(
    'День отсечки аванса',
    'number',
    props.settings.advanceCutoffDay,
    (val) => props.onUpdate({ advanceCutoffDay: parseInt(val) }),
    { min: 1, max: 28 }
  );
  panel.appendChild(cutoffGroup);
  
  // Inclusive Date Switch (NEW)
  const inclusiveSwitch = createSwitch({
    checked: props.settings.isAdvanceDateInclusive,
    onChange: (checked) => props.onUpdate({ isAdvanceDateInclusive: checked }),
    label: 'Дата отсечки включительно',
  });
  const inclusiveGroup = document.createElement('div');
  inclusiveGroup.className = 'setting-group';
  inclusiveGroup.appendChild(inclusiveSwitch);
  panel.appendChild(inclusiveGroup);
  
  // Account Shortened Switch
  const shortenedSwitch = createSwitch({
    checked: props.settings.accountShortened,
    onChange: (checked) => props.onUpdate({ accountShortened: checked }),
    label: 'Учитывать сокращённые дни',
  });
  const shortenedGroup = document.createElement('div');
  shortenedGroup.className = 'setting-group';
  shortenedGroup.appendChild(shortenedSwitch);
  panel.appendChild(shortenedGroup);
  
  // Standard Hours
  const hoursGroup = createInputGroup(
    'Норма часов в неделю',
    'number',
    props.settings.standardHours,
    (val) => props.onUpdate({ standardHours: parseInt(val) }),
    { min: 1, max: 60 }
  );
  panel.appendChild(hoursGroup);
  
  return panel;
}

function createInputGroup(
  label: string,
  type: string,
  value: number,
  onChange: (val: string) => void,
  attrs: { min?: number; max?: number; step?: number } = {}
): HTMLElement {
  const group = document.createElement('div');
  group.className = 'setting-group';
  
  const inputLabel = document.createElement('label');
  inputLabel.textContent = label;
  
  const input = document.createElement('input');
  input.type = type;
  input.className = 'input';
  input.value = String(value);
  
  if (attrs.min !== undefined) input.min = String(attrs.min);
  if (attrs.max !== undefined) input.max = String(attrs.max);
  if (attrs.step !== undefined) input.step = String(attrs.step);
  
  input.addEventListener('change', (e) => {
    onChange((e.target as HTMLInputElement).value);
  });
  
  group.appendChild(inputLabel);
  group.appendChild(input);
  
  return group;
}
