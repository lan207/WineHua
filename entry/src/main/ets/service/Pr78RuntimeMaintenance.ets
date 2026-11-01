// Task-only maintenance HAP. This file is not part of either product PR.
import { Want } from '@kit.AbilityKit';
import { fileIo as fs } from '@kit.CoreFileKit';
import { cryptoFramework } from '@kit.CryptoArchitectureKit';
import modeNapi from 'libpr78_maintenance.so';

const FILES = '/data/storage/el2/base/files';
const BASE_SHA = '0aa1eac9b72376ea5094441b5d5b27067b1266dcd275c442d5148e0960404e0c';
const WORK = `${FILES}/.pr78-maintenance`;
const WINE = `${FILES}/wine`;
const STAGE = `${FILES}/.pr78-runtime-stage/wine`;
const BACKUP = `${FILES}/.pr78-runtime-backup`;
const MARKER = '.winehua-runtime-manifest.json';
const PROBE = `${FILES}/.pr78-runtime-fs-20261101`;
const NONCE = 'winehua-pr78-owned-runtime-filesystem-probe-20261101';

interface RuntimeMarker { payloadSha256: string; }
interface RuntimePlan { payloadSha256: string; files: Record<string, string>; executable: string[]; }
interface VerifiedRuntime { payloadSha256: string; planSha256: string; count: number; }
interface MaintenanceResult {
  status: string; action: string; requestId: string; message: string;
  count: number; oldSha?: string; newSha?: string;
}

export class Pr78RuntimeMaintenance {
  private static instance: Pr78RuntimeMaintenance | null = null;
  static getInstance(): Pr78RuntimeMaintenance {
    if (!Pr78RuntimeMaintenance.instance) Pr78RuntimeMaintenance.instance = new Pr78RuntimeMaintenance();
    return Pr78RuntimeMaintenance.instance;
  }
  private busy: boolean = false;
  private verified: VerifiedRuntime | null = null;

  private exists(path: string): boolean {
    try { fs.lstatSync(path); return true; } catch (_) { return false; }
  }
  private require(condition: boolean, message: string): void {
    if (!condition) throw new Error(message);
  }
  private directory(path: string): void {
    const stat = fs.lstatSync(path);
    this.require(stat.isDirectory() && !stat.isSymbolicLink(), 'Expected a regular managed directory');
  }
  private read(path: string): string { return fs.readTextSync(path); }
  private write(path: string, text: string): void {
    const file = fs.openSync(path, fs.OpenMode.READ_WRITE | fs.OpenMode.CREATE | fs.OpenMode.TRUNC);
    try { fs.writeSync(file.fd, text); fs.fsyncSync(file.fd); } finally { fs.closeSync(file); }
  }
  private marker(path: string): string {
    this.directory(path);
    this.require(!fs.lstatSync(`${path}/${MARKER}`).isSymbolicLink(), 'Linked runtime marker rejected');
    const marker = JSON.parse(this.read(`${path}/${MARKER}`)) as RuntimeMarker;
    this.require(/^[a-f0-9]{64}$/.test(marker.payloadSha256), 'Invalid runtime marker');
    return marker.payloadSha256;
  }
  private relative(path: string): boolean {
    return path.length > 0 && path.length < 1024 && !path.includes('\\') && !path.includes(':') &&
      path.split('/').every((part: string) => part.length > 0 && part !== '.' && part !== '..');
  }
  private files(path: string, relative: string, output: string[]): void {
    this.directory(path);
    for (const name of fs.listFileSync(path)) {
      const child = relative ? `${relative}/${name}` : name;
      this.require(this.relative(child), 'Unsafe staged path');
      const stat = fs.lstatSync(`${path}/${name}`);
      this.require(!stat.isSymbolicLink(), 'Linked staged member rejected');
      if (stat.isDirectory()) this.files(`${path}/${name}`, child, output);
      else { this.require(stat.isFile(), 'Non-file staged member rejected'); output.push(child); }
    }
  }
  private hex(bytes: Uint8Array): string {
    let value = '';
    for (let i = 0; i < bytes.length; i++) value += bytes[i].toString(16).padStart(2, '0');
    return value;
  }
  private async hash(path: string, buffer: ArrayBuffer): Promise<string> {
    const digest = cryptoFramework.createMd('SHA256');
    const size = fs.lstatSync(path).size;
    const file = fs.openSync(path, fs.OpenMode.READ_ONLY);
    try {
      let position = 0;
      while (position < size) {
        const count = fs.readSync(file.fd, buffer, { offset: position, length: Math.min(buffer.byteLength, size-position) });
        this.require(count > 0, 'Unexpected end of staged file');
        await digest.update({ data: new Uint8Array(buffer, 0, count) });
        position += count;
      }
      return this.hex((await digest.digest()).data);
    } finally { fs.closeSync(file); }
  }
  private result(id: string, action: string, status: string, message: string, count: number = 0): MaintenanceResult {
    return { requestId: id, action, status, message, count };
  }
  private report(result: MaintenanceResult): void {
    this.write(`${WORK}/result-${result.requestId}.json`, JSON.stringify(result));
  }
  private recoverInterruptedSwap(): void {
    if (!this.exists(WINE) && this.exists(BACKUP)) {
      this.require(this.marker(BACKUP) === BASE_SHA, 'Unknown backup; recovery refused');
      fs.renameSync(BACKUP, WINE);
    }
  }
  async handle(want: Want): Promise<void> {
    const params = want.parameters;
    const id = params && params['winehua.maintenance.id'] ? `${params['winehua.maintenance.id']}` : 'auto';
    if (!/^[a-zA-Z0-9_-]{1,64}$/.test(id)) return;
    const action = params && params['winehua.maintenance.action'] ? `${params['winehua.maintenance.action']}` : 'inspect';
    if (!this.exists(WORK)) fs.mkdirSync(WORK);
    if (this.busy) { this.report(this.result(id, action, 'FAIL', 'A maintenance operation is already running')); return; }
    this.busy = true;
    try {
      this.recoverInterruptedSwap();
      this.report(this.result(id, action, 'RUNNING', 'Operation started'));
      const result = await this.perform(id, action);
      this.report(result);
    } catch (error) {
      this.report(this.result(id, action, 'FAIL', `${error}`));
    } finally { this.busy = false; }
  }
  private async validateStage(id: string, action: string, plan: RuntimePlan): Promise<number> {
    this.require(/^[a-f0-9]{64}$/.test(plan.payloadSha256) && plan.payloadSha256 !== BASE_SHA, 'Invalid candidate hash');
    this.require(this.marker(STAGE) === plan.payloadSha256, 'Stage marker mismatch');
    const names = Object.keys(plan.files).sort();
    this.require(names.length > 0 && names.length < 50000, 'Invalid candidate file count');
    for (const required of ['bin/wine', 'bin/ntdll.so', 'bin/x86_64-unix/winex11.so',
      'bin/x86_64-windows/ntdll.dll', 'bin/i386-windows/ntdll.dll',
      'dxvk/legacy/x64/d3d9.dll', 'dxvk/legacy/x86/d3d9.dll', 'share/wine/wine.inf', MARKER]) {
      this.require(names.includes(required), 'Candidate lacks a required Wine runtime member');
    }
    const actual: string[] = [];
    this.files(STAGE, '', actual);
    this.require(JSON.stringify(actual.sort()) === JSON.stringify(names), 'Staged file inventory differs from plan');
    const buffer = new ArrayBuffer(1024*1024);
    for (let i = 0; i < names.length; i++) {
      const name = names[i];
      this.require(this.relative(name) && /^[a-f0-9]{64}$/.test(plan.files[name]), 'Invalid manifest member');
      this.require(await this.hash(`${STAGE}/${name}`, buffer) === plan.files[name], `Readback mismatch: ${name}`);
      if (!(i % 100)) this.report(this.result(id, action, 'RUNNING', 'Checking staged runtime files', i));
    }
    for (const name of plan.executable) {
      this.require(this.relative(name) && names.includes(name), 'Invalid executable member');
      this.require(modeNapi.makeExecutable(name), 'Could not set staged executable mode');
    }
    return names.length;
  }
  private async perform(id: string, action: string): Promise<MaintenanceResult> {
    if (action === 'inspect' || action === 'prepare') {
      if (action === 'prepare' && !this.exists(`${FILES}/.pr78-runtime-stage`)) fs.mkdirSync(`${FILES}/.pr78-runtime-stage`);
      const result = this.result(id, action, 'PASS', 'Maintenance-only application; engine is not started');
      result.oldSha = this.exists(WINE) ? this.marker(WINE) : '';
      return result;
    }
    if (action === 'probe') {
      this.directory(PROBE);
      this.require(!this.exists(`${PROBE}.moved`), 'Probe destination already exists');
      this.require(this.read(`${PROBE}/probe.txt`).trim() === NONCE, 'Unknown probe file');
      try {
        fs.renameSync(PROBE, `${PROBE}.moved`);
        this.require(this.read(`${PROBE}.moved/probe.txt`).trim() === NONCE, 'Probe readback mismatch');
        fs.renameSync(`${PROBE}.moved`, PROBE);
      } finally {
        if (this.exists(`${PROBE}.moved`) && !this.exists(PROBE)) fs.renameSync(`${PROBE}.moved`, PROBE);
      }
      fs.unlinkSync(`${PROBE}/probe.txt`);
      fs.rmdirSync(PROBE);
      return this.result(id, action, 'PASS', 'Owned-directory forward/reverse move and cleanup passed');
    }
    if (action === 'verify') {
      this.verified = null;
      this.require(this.marker(WINE) === BASE_SHA, 'Device base differs from the recorded runtime');
      this.require(!this.exists(BACKUP), 'Existing backup must be reviewed first');
      const plan = JSON.parse(this.read(`${WORK}/plan.json`)) as RuntimePlan;
      const count = await this.validateStage(id, action, plan);
      this.verified = { payloadSha256: plan.payloadSha256,
        planSha256: await this.hash(`${WORK}/plan.json`, new ArrayBuffer(1024*1024)), count };
      this.write(`${WORK}/verified.json`, JSON.stringify(this.verified));
      const result = this.result(id, action, 'PASS', 'All staged runtime files read back and hash-verified', count);
      result.newSha = plan.payloadSha256;
      return result;
    }
    if (action === 'commit') {
      const verified = this.verified;
      this.require(verified !== null, 'Verify in this maintenance process before committing');
      if (!verified) throw new Error('No verification');
      this.require(this.marker(WINE) === BASE_SHA && !this.exists(BACKUP), 'Base or backup changed');
      this.require(this.marker(STAGE) === verified.payloadSha256, 'Stage marker changed');
      this.require(await this.hash(`${WORK}/plan.json`, new ArrayBuffer(1024*1024)) === verified.planSha256, 'Verification plan changed');
      const plan = JSON.parse(this.read(`${WORK}/plan.json`)) as RuntimePlan;
      this.require(plan.payloadSha256 === verified.payloadSha256, 'Candidate changed');
      await this.validateStage(id, action, plan);
      // No await between the two moves. Restore the old managed runtime if
      // the second move fails. The prefix and game directories are off-limits.
      fs.renameSync(WINE, BACKUP);
      try { fs.renameSync(STAGE, WINE); }
      catch (error) { fs.renameSync(BACKUP, WINE); throw new Error(`${error}`); }
      const result = this.result(id, action, 'PASS', 'Managed runtime switched; old runtime retained', verified.count);
      result.oldSha = BASE_SHA; result.newSha = verified.payloadSha256;
      this.write(`${WORK}/transaction.json`, JSON.stringify(result));
      this.verified = null;
      return result;
    }
    if (action === 'rollback') {
      const verified = JSON.parse(this.read(`${WORK}/verified.json`)) as VerifiedRuntime;
      this.require(this.marker(BACKUP) === BASE_SHA && this.marker(WINE) === verified.payloadSha256, 'Unknown runtime/backup pair');
      const failed = `${FILES}/.pr78-runtime-failed-${id}`;
      this.require(!this.exists(failed), 'Failure archive already exists');
      fs.renameSync(WINE, failed);
      try { fs.renameSync(BACKUP, WINE); }
      catch (error) { fs.renameSync(failed, WINE); throw new Error(`${error}`); }
      this.verified = null;
      const result = this.result(id, action, 'PASS', 'Previous managed runtime restored; failed candidate retained');
      result.oldSha = verified.payloadSha256; result.newSha = BASE_SHA;
      return result;
    }
    throw new Error('Unknown maintenance action');
  }
}
