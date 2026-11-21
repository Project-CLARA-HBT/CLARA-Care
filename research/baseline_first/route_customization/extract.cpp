#include <routingkit/osm_simple.h>
#include <routingkit/vector_io.h>
#include <string>

int main(int argc, char** argv) {
    if (argc != 3) return 1;
    const auto graph = RoutingKit::simple_load_osm_car_routing_graph_from_pbf(argv[1]);
    const std::string prefix = argv[2];
    RoutingKit::save_vector(prefix + ".first", graph.first_out);
    RoutingKit::save_vector(prefix + ".head", graph.head);
    RoutingKit::save_vector(prefix + ".from", graph.forbidden_turn_from_arc);
    RoutingKit::save_vector(prefix + ".to", graph.forbidden_turn_to_arc);
    RoutingKit::save_vector(prefix + ".time", graph.travel_time);
    RoutingKit::save_vector(prefix + ".lat", graph.latitude);
    RoutingKit::save_vector(prefix + ".lon", graph.longitude);
}
