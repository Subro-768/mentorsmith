package app.mentorsmith.android.focus

import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.provider.Settings
import androidx.core.app.NotificationManagerCompat

/**
 * Focus mode, the Android half.
 *
 * Android has a real, supported answer to "stop all distracting apps":
 * **Do Not Disturb**. Setting the interruption filter to priority-only
 * silences notifications from every application on the phone, and the
 * system shows the moon in the status bar so nothing looks broken.
 *
 * What it does *not* do is close other apps. No Android application may
 * kill another application, and one that claimed otherwise would be lying.
 * What Do Not Disturb does is remove the reason to pick the phone up: the
 * ping from a chat app stops arriving.
 *
 * One permission is needed, and the user grants it - the app cannot take
 * it. **Notification policy access** is what allows an app to change the
 * interruption filter at all.
 */
object FocusMode {

    /** How long a session lasts, by default. */
    const val DEFAULT_MINUTES = 45

    /**
     * Whether the user has granted notification policy access.
     *
     * Without it, [setDoNotDisturb] does nothing and the screen says so
     * rather than pretending a session started.
     */
    fun hasPolicyAccess(context: Context): Boolean {
        val manager = context.getSystemService(NotificationManager::class.java)
        return manager?.isNotificationPolicyAccessGranted == true
    }

    /**
     * The intent that opens the system's notification policy settings.
     *
     * The user grants access there; the app cannot grant it for them.
     */
    fun policyAccessIntent(): Intent =
        Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

    /**
     * The filter currently in force, so it can be put back afterwards.
     */
    fun currentFilter(context: Context): Int {
        val manager = context.getSystemService(NotificationManager::class.java)
        return manager?.currentInterruptionFilter
            ?: NotificationManager.INTERRUPTION_FILTER_ALL
    }

    /**
     * Turn Do Not Disturb on.
     *
     * @return true when the filter was actually changed.
     */
    fun setDoNotDisturb(context: Context): Boolean {
        if (!hasPolicyAccess(context)) return false
        val manager = context.getSystemService(NotificationManager::class.java) ?: return false
        return try {
            manager.setInterruptionFilter(NotificationManager.INTERRUPTION_FILTER_PRIORITY)
            true
        } catch (_: SecurityException) {
            false
        }
    }

    /**
     * Put the previous filter back.
     *
     * Called when the session ends, so a learner who had Do Not Disturb on
     * before keeps it, and one who did not does not get it left on.
     */
    fun restoreFilter(context: Context, previous: Int) {
        if (!hasPolicyAccess(context)) return
        val manager = context.getSystemService(NotificationManager::class.java) ?: return
        try {
            manager.setInterruptionFilter(previous)
        } catch (_: SecurityException) {
            // The policy was revoked while the session ran. Nothing to do.
        }
    }

    /**
     * Whether Do Not Disturb is on right now.
     */
    fun isDoNotDisturbOn(context: Context): Boolean {
        val manager = context.getSystemService(NotificationManager::class.java)
        return manager?.currentInterruptionFilter ==
            NotificationManager.INTERRUPTION_FILTER_PRIORITY
    }

    /**
     * Whether the app may post the notification that shows the session is
     * running.
     */
    fun canPostNotifications(context: Context): Boolean {
        return NotificationManagerCompat.from(context).areNotificationsEnabled()
    }
}
