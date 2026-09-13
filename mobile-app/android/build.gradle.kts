allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

val newBuildDir: Directory =
    rootProject.layout.buildDirectory
        .dir("../../build")
        .get()
rootProject.layout.buildDirectory.value(newBuildDir)

subprojects {
    val newSubprojectBuildDir: Directory = newBuildDir.dir(project.name)
    project.layout.buildDirectory.value(newSubprojectBuildDir)
}
subprojects {
    project.evaluationDependsOn(":app")
}

// El "lintVital*" que Gradle corre automaticamente antes de assembleRelease en el
// modulo stripe_android (dependencia transitiva del plugin flutter_stripe) intenta
// resolver com.google.android.gms:play-services-tapandpay:17.1.2, version que ya
// no esta publicada en los repositorios configurados, y falla el build release
// aunque nuestro codigo no tenga errores. Se desactivan esos checks "vital" (no
// afecta al `flutter analyze` normal de Dart, solo al lint nativo de Android).
subprojects {
    tasks.matching { it.name.startsWith("lintVital") }.configureEach { enabled = false }
}

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}
