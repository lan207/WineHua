@Entry
@Component
struct Pr78Maintenance {
  build() {
    Column({ space: 16 }) {
      Text('正在验证兼容性更新').fontSize(24).fontColor('#ffffff')
      Text('请保持 USB 连接，现有游戏和存档会保留。').fontSize(16).fontColor('#c4d0dc')
    }.width('100%').height('100%').justifyContent(FlexAlign.Center).backgroundColor('#15202e')
  }
}
