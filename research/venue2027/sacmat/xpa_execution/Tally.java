import java.lang.instrument.*;
import java.security.ProtectionDomain;
import java.util.*;
import jdk.internal.org.objectweb.asm.*;

/** Count entries without changing the return value or invoking a policy evaluator. */
public class Tally {
    private static String phase = "startup";
    private static final Map<String, Integer> counts = new TreeMap<>();
    public static void phase(String name) { phase = name; }
    public static synchronized void hit(String method) {
        String key = phase + "," + method;
        counts.put(key, counts.getOrDefault(key, 0) + 1);
    }
    public static void premain(String args, Instrumentation instrument) {
        Runtime.getRuntime().addShutdownHook(new Thread(() ->
            counts.forEach((key, count) -> System.out.println("TALLY," + key + "," + count))));
        instrument.addTransformer(new ClassFileTransformer() {
            public byte[] transform(ClassLoader loader, String type, Class<?> redefined,
                                    ProtectionDomain domain, byte[] bytes) {
                if (!"org/seal/xacml/utils/XACMLElementUtil".equals(type) &&
                    !"org/seal/xacml/semanticCoverage/PolicyRunner".equals(type)) return null;
                ClassReader reader = new ClassReader(bytes);
                ClassWriter writer = new ClassWriter(reader, ClassWriter.COMPUTE_MAXS);
                reader.accept(new ClassVisitor(Opcodes.ASM5, writer) {
                    public MethodVisitor visitMethod(int access, String name, String descriptor,
                                                     String signature, String[] exceptions) {
                        MethodVisitor original = super.visitMethod(access, name, descriptor, signature, exceptions);
                        if (!(name.equals("ConditionEvaluate") || name.equals("TargetEvaluate") ||
                              name.equals("evaluate"))) return original;
                        return new MethodVisitor(Opcodes.ASM5, original) {
                            public void visitCode() {
                                super.visitCode();
                                super.visitLdcInsn(name);
                                super.visitMethodInsn(Opcodes.INVOKESTATIC, "Tally", "hit",
                                                       "(Ljava/lang/String;)V", false);
                            }
                        };
                    }
                }, 0);
                return writer.toByteArray();
            }
        });
    }
}
