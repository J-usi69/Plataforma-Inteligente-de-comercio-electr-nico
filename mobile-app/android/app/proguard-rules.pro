# La app no usa la funcion de "push provisioning" (agregar tarjeta a Google/Apple
# Pay) del SDK de Stripe, pero una de sus dependencias transitivas la referencia
# igual. R8 falla al minificar release porque esas clases no estan presentes.
# Reglas generadas por el propio Android Gradle Plugin para este caso.
-dontwarn com.stripe.android.pushProvisioning.PushProvisioningActivity$g
-dontwarn com.stripe.android.pushProvisioning.PushProvisioningActivityStarter$Args
-dontwarn com.stripe.android.pushProvisioning.PushProvisioningActivityStarter$Error
-dontwarn com.stripe.android.pushProvisioning.PushProvisioningActivityStarter
-dontwarn com.stripe.android.pushProvisioning.PushProvisioningEphemeralKeyProvider
