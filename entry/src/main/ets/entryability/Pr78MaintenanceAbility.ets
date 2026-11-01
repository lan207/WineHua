import { AbilityConstant, UIAbility, Want } from '@kit.AbilityKit';
import { window } from '@kit.ArkUI';
import { Pr78RuntimeMaintenance } from '../service/Pr78RuntimeMaintenance';

export default class Pr78MaintenanceAbility extends UIAbility {
  onCreate(want: Want, _launch: AbilityConstant.LaunchParam): void {
    Pr78RuntimeMaintenance.getInstance().handle(want, this.context);
  }
  onNewWant(want: Want, _launch: AbilityConstant.LaunchParam): void {
    Pr78RuntimeMaintenance.getInstance().handle(want, this.context);
  }
  onWindowStageCreate(stage: window.WindowStage): void {
    stage.getMainWindowSync().setWindowKeepScreenOn(true);
    stage.loadContent('pages/Pr78Maintenance');
  }
}
