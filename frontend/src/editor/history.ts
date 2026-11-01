import { HISTORY_LIMIT } from "./constants";

/** Snapshot-based undo/redo. States are JSON strings, so a change is cheap to
 *  detect (string equality) and impossible to alias by accident. */
export class History {
  private stack: string[] = [];
  private index = -1;

  reset(state: string): void {
    this.stack = [state];
    this.index = 0;
  }

  push(state: string): boolean {
    if (this.stack[this.index] === state) return false;
    this.stack = this.stack.slice(0, this.index + 1);
    this.stack.push(state);
    if (this.stack.length > HISTORY_LIMIT) this.stack.shift();
    this.index = this.stack.length - 1;
    return true;
  }

  undo(): string | null {
    if (this.index <= 0) return null;
    this.index -= 1;
    return this.stack[this.index];
  }

  redo(): string | null {
    if (this.index >= this.stack.length - 1) return null;
    this.index += 1;
    return this.stack[this.index];
  }

  get canUndo(): boolean {
    return this.index > 0;
  }

  get canRedo(): boolean {
    return this.index < this.stack.length - 1;
  }
}
