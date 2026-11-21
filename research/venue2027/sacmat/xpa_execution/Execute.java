import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import org.seal.xacml.coverage.MCDC;
import org.seal.xacml.policyUtils.PolicyLoader;
import org.seal.xacml.semanticCoverage.PolicyRunner;
import org.wso2.balana.AbstractPolicy;

/** Exercise only the conference example and the unmodified MC/DC generator. */
public class Execute {
    static String decide(AbstractPolicy policy, String xml) {
        String[] outcomes = {"Permit", "Deny", "Indeterminate", "NotApplicable", "ID", "IP", "IDP"};
        int outcome = PolicyRunner.evaluate(policy, xml);
        if (outcome < 0 || outcome >= outcomes.length)
            throw new IllegalStateException("Unrecognized decision " + outcome);
        return outcomes[outcome];
    }
    public static void main(String[] args) throws Exception {
        Path fixture = Paths.get(args[0]).toAbsolutePath();
        Path out = Files.createDirectory(Paths.get(args[1]));
        Path policyFile = fixture.resolve("conference3.xml");
        AbstractPolicy policy = PolicyLoader.loadPolicy(policyFile.toFile());
        Path suite = fixture.resolve("test_suites/conference3_MCDCCoverage");
        Tally.phase("reference");
        List<String> replay = new ArrayList<>();
        for (String row : Files.readAllLines(suite.resolve("conference3_MCDCCoverage.csv"))) {
            String[] fields = row.split(",");
            String xml = new String(Files.readAllBytes(suite.resolve(fields[0])), StandardCharsets.UTF_8);
            replay.add(fields[0] + "," + fields[1] + "," + decide(policy, xml));
        }
        Files.write(out.resolve("reference.csv"), replay, StandardCharsets.UTF_8);
        Tally.phase("generation");
        MCDC generator = new MCDC(policyFile.toString(), true);
        List<String> requests = generator.generateTests();
        Tally.phase("replay");
        List<String> generated = new ArrayList<>();
        for (String xml : requests) {
            String name = String.format("request-%03d.xml", generated.size() + 1);
            Files.write(out.resolve(name), xml.getBytes(StandardCharsets.UTF_8));
            generated.add(name + "," + decide(policy, xml));
        }
        Files.write(out.resolve("generated.csv"), generated, StandardCharsets.UTF_8);
    }
}
