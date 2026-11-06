// Undo/Redo kiểu command pattern. Mỗi command: { label, do(), undo() }.
// Người mới dám thử mọi thứ vì luôn quay lại được.
export class CommandStack extends EventTarget {
  constructor(limit = 100) {
    super();
    this.limit = limit;
    this.undoStack = [];
    this.redoStack = [];
  }

  /** Thực thi rồi ghi lại. */
  execute(cmd) {
    cmd.do();
    this.push(cmd);
  }

  /** Ghi lại command ĐÃ được áp dụng (vd. kéo gizmo xong). */
  push(cmd) {
    this.undoStack.push(cmd);
    if (this.undoStack.length > this.limit) this.undoStack.shift();
    this.redoStack = [];
    this.emit();
  }

  undo() {
    const cmd = this.undoStack.pop();
    if (!cmd) return null;
    cmd.undo();
    this.redoStack.push(cmd);
    this.emit();
    return cmd;
  }

  redo() {
    const cmd = this.redoStack.pop();
    if (!cmd) return null;
    cmd.do();
    this.undoStack.push(cmd);
    this.emit();
    return cmd;
  }

  get canUndo() { return this.undoStack.length > 0; }
  get canRedo() { return this.redoStack.length > 0; }

  emit() {
    this.dispatchEvent(new Event('change'));
  }
}
