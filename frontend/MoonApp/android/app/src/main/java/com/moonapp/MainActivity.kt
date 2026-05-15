package com.moonapp

import com.facebook.react.ReactActivity
import com.facebook.react.ReactActivityDelegate
import com.facebook.react.defaults.DefaultNewArchitectureEntryPoint.fabricEnabled
import com.facebook.react.defaults.DefaultReactActivityDelegate
import com.moonapp.widget.WidgetMicActionReceiver

class MainActivity : ReactActivity() {

  /**
   * Returns the name of the main component registered from JavaScript. This is used to schedule
   * rendering of the component.
   */
  override fun getMainComponentName(): String = "MoonApp"

  /**
   * Returns the instance of the [ReactActivityDelegate]. We use [DefaultReactActivityDelegate]
   * which allows you to enable New Architecture with a single boolean flags [fabricEnabled]
   */
  override fun createReactActivityDelegate(): ReactActivityDelegate =
      DefaultReactActivityDelegate(this, mainComponentName, fabricEnabled)

  // 잠금화면 위젯 "질문하기" 탭이 발생했을 때 ReactContext가 아직 안 떠 있어서
  // 이벤트가 드랍됐을 경우, 사용자가 앱을 열 때 한 번 더 시도한다.
  override fun onResume() {
    super.onResume()
    WidgetMicActionReceiver.tryConsumePendingTrigger(this)
  }
}
